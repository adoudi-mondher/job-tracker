import re
from datetime import datetime, timedelta
from functools import wraps

import requests as http_requests
from flask import Blueprint, current_app, jsonify, request

from app import db
from app.models import Candidature, Entreprise, Interaction

api_bp = Blueprint("api", __name__)


def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {current_app.config['APP_PASSWORD']}"
        if auth != expected:
            return jsonify({"error": "Non autorisé"}), 401
        return f(*args, **kwargs)

    return decorated


@api_bp.route("/candidatures", methods=["GET"])
@api_key_required
def get_candidatures():
    """
    Liste les candidatures actives (non archivees) — utilise par n8n.
    Filtre optionnel : ?url=<lien_offre> pour verifier la deduplication (W1).
    """
    url_filter = request.args.get("url")
    query = Candidature.query.filter(Candidature.archived_at.is_(None))
    if url_filter:
        query = query.filter(Candidature.lien_offre == url_filter)
    candidatures = query.all()
    return jsonify([c.to_dict() for c in candidatures])


@api_bp.route("/candidatures", methods=["POST"])
@api_key_required
def create_candidature():
    """
    Cree une candidature depuis n8n (scraping automatique — W1).
    Payload JSON attendu :
      entreprise_nom (str, requis), poste (str, requis),
      lien_offre (str), type_contrat (str), notes (str),
      source (str, defaut "auto")
    """
    data = request.get_json(force=True) or {}

    entreprise_nom = data.get("entreprise_nom", "").strip()
    poste = data.get("poste", "").strip()
    if not entreprise_nom or not poste:
        return jsonify({"error": "entreprise_nom et poste sont requis"}), 400

    # Trouver ou creer l'entreprise
    entreprise = Entreprise.query.filter_by(nom=entreprise_nom).first()
    if not entreprise:
        entreprise = Entreprise(
            nom=entreprise_nom,
            localisation=data.get("localisation"),
            secteur=data.get("secteur"),
        )
        db.session.add(entreprise)
        db.session.flush()  # obtenir l'id sans commit

    today = datetime.utcnow().date()
    candidature = Candidature(
        entreprise_id=entreprise.id,
        poste=poste,
        type_contrat=data.get("type_contrat", "Alternance"),
        date_envoi=today,
        date_relance=today + timedelta(days=7),
        statut="À envoyer",
        lien_offre=data.get("lien_offre"),
        notes=data.get("notes"),
        source=data.get("source", "auto"),
    )
    db.session.add(candidature)
    db.session.commit()
    return jsonify(candidature.to_dict()), 201


@api_bp.route("/candidatures/relances", methods=["GET"])
@api_key_required
def get_relances():
    """Retourne les candidatures actives dont la relance est due."""
    toutes = Candidature.query.filter(
        Candidature.statut == "Envoyée", Candidature.archived_at.is_(None)
    ).all()
    dues = [c.to_dict() for c in toutes if c.relance_due]
    return jsonify(dues)


@api_bp.route("/candidatures/<int:id>", methods=["GET"])
@api_key_required
def get_candidature(id):
    """Retourne une candidature par son id — utilise par n8n W3."""
    candidature = Candidature.query.get_or_404(id)
    return jsonify(candidature.to_dict())


@api_bp.route("/candidatures/<int:id>", methods=["PATCH"])
@api_key_required
def patch_candidature(id):
    """
    Mise a jour partielle par n8n — enrichissement W2 et lettre W3.
    Champs acceptes :
      poste, stack_technique, resume_offre, lettre_motivation, notes,
      statut, lien_offre, source
    Les champs absents du payload ne sont pas modifies.
    """
    candidature = Candidature.query.get_or_404(id)
    data = request.get_json(force=True) or {}

    PATCHABLE = [
        "poste", "stack_technique", "resume_offre",
        "lettre_motivation", "notes", "statut", "lien_offre", "source",
    ]
    for field in PATCHABLE:
        if field in data:
            if field == "statut" and data[field] not in Candidature.STATUTS:
                return jsonify({"error": f"Statut invalide : {data[field]}"}), 400
            setattr(candidature, field, data[field])

    db.session.commit()
    return jsonify(candidature.to_dict())


@api_bp.route("/candidatures/digest", methods=["GET"])
@api_key_required
def get_digest():
    """
    Donnees agregees pour le digest Telegram hebdomadaire (W4).
    Retourne :
      new_this_week    : offres creees dans les 7 derniers jours
      pending_followup : candidatures sans reponse depuis +7 jours (statut Envoyee)
      in_progress      : candidatures avec statut actif (Relance, Entretien)
    """
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)

    new_this_week = Candidature.query.filter(
        Candidature.archived_at.is_(None),
        Candidature.date_envoi >= week_ago,
    ).all()

    pending_followup = Candidature.query.filter(
        Candidature.archived_at.is_(None),
        Candidature.statut == "Envoyée",
        Candidature.date_relance <= today,
    ).all()

    in_progress = Candidature.query.filter(
        Candidature.archived_at.is_(None),
        Candidature.statut.in_(["Relance", "Entretien"]),
    ).all()

    return jsonify({
        "new_this_week": [c.to_dict() for c in new_this_week],
        "pending_followup": [c.to_dict() for c in pending_followup],
        "in_progress": [c.to_dict() for c in in_progress],
    })


@api_bp.route("/candidatures/<int:id>/statut", methods=["PUT"])
@api_key_required
def update_statut(id):
    candidature = Candidature.query.get_or_404(id)
    data = request.get_json()
    nouveau_statut = data.get("statut")
    if nouveau_statut not in Candidature.STATUTS:
        return jsonify(
            {"error": f"Statut invalide. Valeurs acceptées : {Candidature.STATUTS}"}
        ), 400
    candidature.statut = nouveau_statut
    db.session.commit()
    return jsonify(candidature.to_dict())


@api_bp.route("/candidatures/<int:id>/interactions", methods=["POST"])
@api_key_required
def add_interaction(id):
    candidature = Candidature.query.get_or_404(id)
    data = request.get_json()
    interaction = Interaction(
        candidature_id=id,
        type_interaction=data.get("type_interaction", "Relance"),
        notes=data.get("notes", "Relance automatique via n8n"),
    )
    db.session.add(interaction)
    db.session.commit()
    return jsonify(interaction.to_dict()), 201


# ── W1 : scraping quotidien offres IA alternance ──────────────────────────────


@api_bp.route("/scrape", methods=["POST"])
@api_key_required
def scrape_offres():
    """
    W1 — Déclenché par n8n (Schedule 7h).
    Scrape LBA API (6 villes) + WTTJ RSS + HelloWork RSS.
    Crée les nouvelles candidatures et retourne un rapport JSON.
    """
    CITIES = [
        {"name": "Paris",       "lat": 48.8566, "lon": 2.3522},
        {"name": "Lyon",        "lat": 45.7640, "lon": 4.8357},
        {"name": "Marseille",   "lat": 43.2965, "lon": 5.3698},
        {"name": "Metz",        "lat": 49.1193, "lon": 6.1757},
        {"name": "Nancy",       "lat": 48.6921, "lon": 6.1844},
        {"name": "Strasbourg",  "lat": 48.5734, "lon": 7.7521},
    ]

    RSS_FEEDS = [
        {
            "url": (
                "https://www.welcometothejungle.com/fr/jobs.rss"
                "?query=d%C3%A9veloppeur+ia+alternance"
                "&refinementList%5Bcontract_type_names%5D%5B%5D=Alternance"
            ),
            "src": "WTTJ",
        },
        {
            "url": (
                "https://www.welcometothejungle.com/fr/jobs.rss"
                "?query=llm+rag+nlp+alternance"
                "&refinementList%5Bcontract_type_names%5D%5B%5D=Alternance"
            ),
            "src": "WTTJ",
        },
        {
            "url": (
                "https://www.hellowork.com/rss/emploi"
                "?k=d%C3%A9veloppeur+intelligence+artificielle&c=Alternance"
            ),
            "src": "HelloWork",
        },
        {
            "url": (
                "https://www.hellowork.com/rss/emploi"
                "?k=ia+machine+learning+alternance&c=Alternance"
            ),
            "src": "HelloWork",
        },
    ]

    lba_key = current_app.config.get("LBA_API_KEY", "")

    # Charger les URLs existantes pour déduplication
    existing_urls = {
        c.lien_offre
        for c in Candidature.query.filter(Candidature.lien_offre.isnot(None)).all()
    }
    seen = set(existing_urls)

    report = {"created": 0, "lba": 0, "wttj": 0, "hellowork": 0, "errors": []}

    def _parse_rss(text):
        """Extrait les items d'un flux RSS — gère CDATA et guid/link."""
        items = []
        for m in re.finditer(r"<item>(.*?)</item>", text, re.DOTALL):
            b = m.group(1)
            title_m = re.search(
                r"<title>(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?</title>", b, re.DOTALL
            )
            link_m = re.search(r"<link>\s*(https?://[^\s<]+)\s*</link>", b) or re.search(
                r"<guid[^>]*>\s*(https?://[^\s<]+)\s*</guid>", b
            )
            if title_m and link_m:
                items.append({"title": title_m.group(1).strip(), "link": link_m.group(1).strip()})
        return items

    def _split_title(raw):
        """'Dev IA chez Acme Corp' -> ('Dev IA', 'Acme Corp')"""
        m = re.match(r"^(.*?)\s+(?:chez|@)\s+(.+)$", raw, re.IGNORECASE) or re.match(
            r"^(.*?)\s+-\s+(.+)$", raw
        )
        return (m.group(1).strip(), m.group(2).strip()) if m else (raw.strip(), "")

    def _create(offer, src_key):
        url = offer.get("lien_offre")
        if not url or url in seen:
            return
        seen.add(url)
        # Trouver ou créer l'entreprise
        nom = offer.get("entreprise_nom", "").strip() or "Inconnu"
        entreprise = Entreprise.query.filter_by(nom=nom).first()
        if not entreprise:
            entreprise = Entreprise(nom=nom)
            db.session.add(entreprise)
            db.session.flush()
        today = datetime.utcnow().date()
        c = Candidature(
            entreprise_id=entreprise.id,
            poste=offer.get("poste", "Alternance IA"),
            type_contrat="Alternance",
            date_envoi=today,
            date_relance=today + timedelta(days=7),
            statut="À envoyer",
            lien_offre=url,
            source="auto",
            notes=offer.get("notes", ""),
        )
        db.session.add(c)
        db.session.commit()
        report["created"] += 1
        report[src_key] += 1

    # ── LBA API — 6 villes ────────────────────────────────────────────────────
    for city in CITIES:
        try:
            resp = http_requests.get(
                "https://labonnealternance.apprentissage.beta.gouv.fr/api/v1/jobs",
                params={
                    "romes": "M1805,M1803",
                    "longitude": city["lon"],
                    "latitude": city["lat"],
                    "radius": 30,
                    "caller": "job-tracker-mondher",
                },
                headers={"Authorization": f"Bearer {lba_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            jobs = (data.get("lbaJobs") or {}).get("results", []) + \
                   (data.get("peJobs") or {}).get("results", [])
            for j in jobs:
                job_url = j.get("url") or j.get("apply_url")
                _create(
                    {
                        "entreprise_nom": (j.get("company") or {}).get("name")
                            or j.get("company_name") or city["name"],
                        "poste": j.get("title") or j.get("intitule") or "Alternance IA",
                        "lien_offre": job_url,
                        "notes": f"LBA · {city['name']}",
                    },
                    "lba",
                )
        except Exception as e:
            report["errors"].append(f"LBA-{city['name']}: {e}")

    # ── RSS — WTTJ + HelloWork ────────────────────────────────────────────────
    for feed in RSS_FEEDS:
        src = feed["src"]
        src_key = "wttj" if src == "WTTJ" else "hellowork"
        try:
            resp = http_requests.get(
                feed["url"],
                headers={"User-Agent": "Mozilla/5.0 (compatible; job-tracker-bot/1.0)"},
                timeout=10,
            )
            resp.raise_for_status()
            for item in _parse_rss(resp.text):
                poste, entreprise = _split_title(item["title"])
                _create(
                    {
                        "entreprise_nom": entreprise or src,
                        "poste": poste or item["title"],
                        "lien_offre": item["link"],
                        "notes": f"Source : {src}",
                    },
                    src_key,
                )
        except Exception as e:
            report["errors"].append(f"{src}: {e}")

    return jsonify(report)
