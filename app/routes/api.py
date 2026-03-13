from flask import Blueprint, jsonify, request, current_app
from app import db
from app.models import Candidature, Interaction
from functools import wraps

api_bp = Blueprint('api', __name__)


def api_key_required(f):
    """Vérifie le mot de passe en header Authorization pour n8n"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        expected = f"Bearer {current_app.config['APP_PASSWORD']}"
        if auth != expected:
            return jsonify({'error': 'Non autorisé'}), 401
        return f(*args, **kwargs)
    return decorated


@api_bp.route('/candidatures', methods=['GET'])
@api_key_required
def get_candidatures():
    """Liste toutes les candidatures — utilisé par n8n"""
    candidatures = Candidature.query.all()
    return jsonify([c.to_dict() for c in candidatures])


@api_bp.route('/candidatures/relances', methods=['GET'])
@api_key_required
def get_relances():
    """Retourne les candidatures dont la relance est due — trigger n8n"""
    toutes = Candidature.query.filter_by(statut='Envoyée').all()
    dues = [c.to_dict() for c in toutes if c.relance_due]
    return jsonify(dues)


@api_bp.route('/candidatures/<int:id>/statut', methods=['PUT'])
@api_key_required
def update_statut(id):
    """Modifie le statut d'une candidature — appelé par n8n"""
    candidature = Candidature.query.get_or_404(id)
    data = request.get_json()
    nouveau_statut = data.get('statut')
    if nouveau_statut not in Candidature.STATUTS:
        return jsonify({'error': f'Statut invalide. Valeurs acceptées : {Candidature.STATUTS}'}), 400
    candidature.statut = nouveau_statut
    db.session.commit()
    return jsonify(candidature.to_dict())


@api_bp.route('/candidatures/<int:id>/interactions', methods=['POST'])
@api_key_required
def add_interaction(id):
    """Ajoute une interaction automatique — appelé par n8n après relance"""
    candidature = Candidature.query.get_or_404(id)
    data = request.get_json()
    interaction = Interaction(
        candidature_id   = id,
        type_interaction = data.get('type_interaction', 'Relance'),
        notes            = data.get('notes', 'Relance automatique via n8n'),
    )
    db.session.add(interaction)
    db.session.commit()
    return jsonify(interaction.to_dict()), 201
