from datetime import datetime, timedelta
from functools import wraps

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
