import hmac
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
        if not hmac.compare_digest(auth, expected):
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
        "lettre_motivation", "message_accompagnement", "notes", "statut", "lien_offre", "source",
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


# ── W1 : sonde quotidienne offres IA alternance (sans création automatique) ───

_FT_TARGET_DEPTS_API = {"75", "77", "78", "91", "92", "93", "94", "95",
                        "69", "13", "57", "54", "67"}
_FT_SEARCHES = [
    ("intelligence artificielle", "E2"),
    ("intelligence artificielle", "FS"),
    ("machine learning",          "E2"),
    ("machine learning",          "FS"),
    ("data scientist",            "E2"),
    ("nlp llm rag",               "E2"),
]


@api_bp.route("/scrape", methods=["POST"])
@api_key_required
def scrape_offres():
    """
    W1 — Déclenché par n8n (Schedule 7h).
    Sonde de comptage : retourne le nombre de nouvelles offres disponibles
    sur France Travail sans créer de candidatures.
    L'ajout au pipeline se fait manuellement via /offres/france-travail.
    """
    ft_client_id     = current_app.config.get("FT_CLIENT_ID", "")
    ft_client_secret = current_app.config.get("FT_CLIENT_SECRET", "")
    report = {"available": 0, "already_in_pipeline": 0, "errors": []}

    # Token OAuth2
    try:
        tok = http_requests.post(
            "https://entreprise.francetravail.fr/connexion/oauth2/access_token",
            params={"realm": "/partenaire"},
            data={
                "grant_type": "client_credentials",
                "client_id": ft_client_id,
                "client_secret": ft_client_secret,
                "scope": "api_offresdemploiv2 o2dsoffre",
            },
            timeout=10,
        )
        tok.raise_for_status()
        token = tok.json()["access_token"]
    except Exception as e:
        report["errors"].append(f"FT-token: {e}")
        return jsonify(report)

    ft_headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    # URLs existantes en base
    existing_urls = {
        c.lien_offre
        for c in Candidature.query.filter(Candidature.lien_offre.isnot(None)).all()
    }
    seen_ids: set = set()

    for mots_cles, nature_contrat in _FT_SEARCHES:
        try:
            resp = http_requests.get(
                "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
                headers=ft_headers,
                params={"motsCles": mots_cles, "natureContrat": nature_contrat,
                        "nombreResultats": 150},
                timeout=15,
            )
            resp.raise_for_status()
            for o in resp.json().get("resultats", []):
                if o["id"] in seen_ids:
                    continue
                libelle = (o.get("lieuTravail") or {}).get("libelle", "")
                m = re.match(r"^(\d{2,3})\s*-", libelle)
                dept = m.group(1) if m else None
                if dept and dept not in _FT_TARGET_DEPTS_API:
                    continue
                seen_ids.add(o["id"])
                url = (
                    (o.get("origineOffre") or {}).get("urlOrigine")
                    or f"https://candidat.francetravail.fr/offres/recherche/detail/{o['id']}"
                )
                if url in existing_urls:
                    report["already_in_pipeline"] += 1
                else:
                    report["available"] += 1
        except Exception as e:
            report["errors"].append(f"FT-{nature_contrat}: {e}")

    return jsonify(report)
