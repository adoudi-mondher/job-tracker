import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from app import db
from app.models import Candidature, Entreprise
from app.routes.main import login_required
from app.webhooks import send_webhook
from config import Config
from datetime import datetime, timedelta

offres_bp = Blueprint("offres", __name__)

# ── LBA ───────────────────────────────────────────────────────────────────────

LBA_API_URL = "https://api.apprentissage.beta.gouv.fr/api/job/v1/search"

# Villes cibles — identiques à France Travail
_LBA_CITIES = [
    {"name": "Paris",      "lat": 48.8566, "lon": 2.3522},
    {"name": "Lyon",       "lat": 45.7640, "lon": 4.8357},
    {"name": "Marseille",  "lat": 43.2965, "lon": 5.3698},
    {"name": "Metz",       "lat": 49.1193, "lon": 6.1757},
    {"name": "Nancy",      "lat": 48.6921, "lon": 6.1844},
    {"name": "Strasbourg", "lat": 48.5734, "lon": 7.7521},
]

DEFAULT_ROMES   = "M1806,M1803,M1805"
DEFAULT_RADIUS  = 30
DEFAULT_DIPLOMA = "3"


def _fetch_one_city(lat, lon, radius, romes, diploma):
    """Appel API LBA pour une ville — retourne (jobs, recruiters)."""
    try:
        resp = requests.get(
            LBA_API_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "radius": radius,
                "target_diploma_level": diploma,
                "romes": romes,
            },
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {Config.LBA_API_KEY}",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("jobs", []), data.get("recruiters", [])
    except Exception:
        return [], []


def fetch_offres_all_cities(romes, radius, diploma):
    """
    Interroge l'API LBA pour les 6 villes cibles en parallèle.
    Déduplique les offres par URL et les recruteurs par nom+adresse.
    """
    def _fetch(city):
        return _fetch_one_city(city["lat"], city["lon"], radius, romes, diploma)

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(_fetch, _LBA_CITIES))

    all_jobs: list = []
    all_recruiters: list = []
    seen_job_urls: set = set()
    seen_recruiter_keys: set = set()

    for jobs, recruiters in results:
        for job in jobs:
            url = (job.get("apply") or {}).get("url") or ""
            if url and url in seen_job_urls:
                continue
            if url:
                seen_job_urls.add(url)
            all_jobs.append(job)

        for r in recruiters:
            wp = r.get("workplace") or {}
            key = (
                f"{(wp.get('name') or '').strip()}"
                f"|{((wp.get('location') or {}).get('address') or '').strip()}"
            )
            if key in seen_recruiter_keys:
                continue
            seen_recruiter_keys.add(key)
            all_recruiters.append(r)

    return all_jobs, all_recruiters


@offres_bp.route("/")
@login_required
def index():
    romes   = request.args.get("romes",   DEFAULT_ROMES)
    radius  = request.args.get("radius",  DEFAULT_RADIUS)
    diploma = request.args.get("diploma", DEFAULT_DIPLOMA)
    contrat = request.args.get("contrat", "tous")  # "tous" | "apprentissage" | "professionnalisation"

    jobs, recruiters = fetch_offres_all_cities(romes, radius, diploma)

    # Filtre par type de contrat (client-side — le champ est dans la réponse API)
    if contrat != "tous":
        kw = contrat.lower()
        jobs = [
            j for j in jobs
            if any(kw in (t or "").lower()
                   for t in ((j.get("contract") or {}).get("type") or []))
        ]

    # URLs déjà dans le pipeline → marquage "Déjà ajouté"
    existing_urls = {
        c.lien_offre
        for c in Candidature.query.filter(Candidature.lien_offre.isnot(None)).all()
    }

    return render_template(
        "offres/index.html",
        jobs=jobs,
        recruiters=recruiters,
        romes=romes,
        radius=radius,
        diploma=diploma,
        contrat=contrat,
        existing_urls=existing_urls,
    )


@offres_bp.route("/ajouter", methods=["POST"])
@login_required
def ajouter():
    """Crée entreprise + candidature spontanée depuis un recruteur LBA."""
    nom          = request.form.get("nom")
    localisation = request.form.get("localisation")
    site_web     = request.form.get("site_web") or None
    lien_offre   = request.form.get("lien_offre") or None
    naf_label    = request.form.get("naf_label") or None

    entreprise = Entreprise.query.filter_by(nom=nom).first()
    if not entreprise:
        entreprise = Entreprise(
            nom=nom,
            secteur="ESN",
            localisation=localisation,
            site_web=site_web,
            notes=f"Source : La Bonne Alternance | NAF : {naf_label}"
            if naf_label
            else "Source : La Bonne Alternance",
        )
        db.session.add(entreprise)
        db.session.flush()

    date_envoi = datetime.utcnow().date()
    candidature = Candidature(
        entreprise_id=entreprise.id,
        poste="Candidature spontanée — MOA / PO / Dev",
        type_contrat="Stage",
        date_envoi=date_envoi,
        statut="À envoyer",
        lien_offre=lien_offre,
        date_relance=date_envoi + timedelta(days=7),
        notes="Ajoutée depuis La Bonne Alternance — candidature spontanée",
    )
    db.session.add(candidature)
    db.session.commit()

    flash(f'"{nom}" ajouté au pipeline.', "success")
    return redirect(url_for("offres.index"))


# ── France Travail ────────────────────────────────────────────────────────────

# Cache du token OAuth2 (module-level, partagé entre les workers du même process)
_ft_token_cache: dict = {"token": None, "expires_at": 0.0}

# Départements cibles : IDF + Lyon + Marseille + Metz + Nancy + Strasbourg
_FT_TARGET_DEPTS = {
    "75", "77", "78", "91", "92", "93", "94", "95",
    "69", "13", "57", "54", "67",
}

_FT_NATURE_LABELS = {
    "E2": "Apprentissage",
    "FS": "Professionnalisation",
}


def _get_ft_token(client_id: str, client_secret: str) -> str:
    """Retourne un token OAuth2 France Travail valide (avec cache 25 min)."""
    if _ft_token_cache["token"] and time.time() < _ft_token_cache["expires_at"] - 60:
        return _ft_token_cache["token"]
    resp = requests.post(
        "https://entreprise.francetravail.fr/connexion/oauth2/access_token",
        params={"realm": "/partenaire"},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "api_offresdemploiv2 o2dsoffre",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _ft_token_cache["token"] = data["access_token"]
    _ft_token_cache["expires_at"] = time.time() + data.get("expires_in", 1499)
    return _ft_token_cache["token"]


def _dept_code(libelle: str) -> str | None:
    """Extrait le code département depuis '75 - PARIS 17' → '75'."""
    m = re.match(r"^(\d{2,3})\s*-", libelle or "")
    return m.group(1) if m else None


def fetch_ft_offres(mots_cles: str, nature_contrats: list[str],
                    client_id: str, client_secret: str) -> tuple[list, str | None]:
    """
    Interroge l'API France Travail et retourne les offres filtrées.
    Retourne (offres_normalisées, message_erreur_ou_None).
    """
    try:
        token = _get_ft_token(client_id, client_secret)
    except Exception as e:
        return [], f"Erreur d'authentification France Travail : {e}"

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    all_offres: list[dict] = []
    seen_ids: set[str] = set()

    for nc in nature_contrats:
        try:
            resp = requests.get(
                "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
                headers=headers,
                params={"motsCles": mots_cles, "natureContrat": nc, "nombreResultats": 150},
                timeout=15,
            )
            resp.raise_for_status()
        except Exception:
            continue

        for o in resp.json().get("resultats", []):
            if o["id"] in seen_ids:
                continue
            lieu_libelle = (o.get("lieuTravail") or {}).get("libelle", "")
            dept = _dept_code(lieu_libelle)
            # Garder les offres en zone cible OU sans département précisé ("France", remote)
            if dept and dept not in _FT_TARGET_DEPTS:
                continue
            seen_ids.add(o["id"])
            url = (
                (o.get("origineOffre") or {}).get("urlOrigine")
                or f"https://candidat.francetravail.fr/offres/recherche/detail/{o['id']}"
            )
            all_offres.append({
                "id":            o["id"],
                "titre":         o.get("intitule", ""),
                "entreprise":    (o.get("entreprise") or {}).get("nom") or "Entreprise non précisée",
                "lieu":          lieu_libelle,
                "url":           url,
                "nature":        _FT_NATURE_LABELS.get(nc, nc),
                "nature_code":   nc,
                "date_creation": (o.get("dateCreation") or "")[:10],
            })

    return all_offres, None


@offres_bp.route("/france-travail")
@login_required
def france_travail():
    mots_cles     = request.args.get("mots_cles", "intelligence artificielle")
    nature_choice = request.args.get("nature", "E2")   # "E2" | "FS" | "les_deux"
    nature_contrats = ["E2", "FS"] if nature_choice == "les_deux" else [nature_choice]

    client_id     = current_app.config.get("FT_CLIENT_ID", "")
    client_secret = current_app.config.get("FT_CLIENT_SECRET", "")

    offres, error = fetch_ft_offres(mots_cles, nature_contrats, client_id, client_secret)

    # URLs déjà dans le pipeline → marquer les doublons
    existing_urls = {
        c.lien_offre
        for c in Candidature.query.filter(Candidature.lien_offre.isnot(None)).all()
    }

    return render_template(
        "offres/france_travail.html",
        offres=offres,
        existing_urls=existing_urls,
        mots_cles=mots_cles,
        nature_choice=nature_choice,
        error=error,
    )


@offres_bp.route("/ajouter-ft", methods=["POST"])
@login_required
def ajouter_ft():
    """Crée entreprise + candidature depuis une offre France Travail sélectionnée."""
    poste      = request.form.get("poste", "Alternance IA").strip()
    nom_ent    = (request.form.get("entreprise_nom") or "France Travail").strip()
    lieu       = request.form.get("lieu", "")
    lien_offre = request.form.get("lien_offre") or None
    nature     = request.form.get("nature", "")

    # Entreprise
    entreprise = Entreprise.query.filter_by(nom=nom_ent).first()
    if not entreprise:
        entreprise = Entreprise(
            nom=nom_ent,
            localisation=lieu,
            notes="Source : France Travail",
        )
        db.session.add(entreprise)
        db.session.flush()

    # Candidature
    today = datetime.utcnow().date()
    c = Candidature(
        entreprise_id=entreprise.id,
        poste=poste,
        type_contrat="Alternance",
        date_envoi=today,
        date_relance=today + timedelta(days=7),
        statut="À envoyer",
        lien_offre=lien_offre,
        source="auto",
        notes=f"France Travail · {nature} · {lieu}".rstrip(" ·"),
    )
    db.session.add(c)
    db.session.commit()

    # W2 enrichissement automatique si URL disponible
    if lien_offre:
        send_webhook(
            current_app.config["N8N_WEBHOOK_ENRICH"],
            {"candidature_id": c.id, "url": lien_offre},
        )

    flash(f'"{poste}" ajouté au pipeline.', "success")
    # Retour vers la même page avec les mêmes filtres
    referrer = request.referrer
    return redirect(referrer if referrer else url_for("offres.france_travail"))
