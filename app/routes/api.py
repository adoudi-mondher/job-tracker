from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from app import db
from app.models import Candidature, Interaction

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
    """Liste les candidatures actives (non archivées) — utilisé par n8n."""
    candidatures = Candidature.query.filter(Candidature.archived_at.is_(None)).all()
    return jsonify([c.to_dict() for c in candidatures])


@api_bp.route("/candidatures/relances", methods=["GET"])
@api_key_required
def get_relances():
    """Retourne les candidatures actives dont la relance est due."""
    toutes = Candidature.query.filter(
        Candidature.statut == "Envoyée", Candidature.archived_at.is_(None)
    ).all()
    dues = [c.to_dict() for c in toutes if c.relance_due]
    return jsonify(dues)


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
