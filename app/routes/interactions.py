from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from app import db
from app.models import Interaction, Candidature
from app.routes.main import login_required

interactions_bp = Blueprint('interactions', __name__)


@interactions_bp.route('/nouvelle/<int:candidature_id>', methods=['GET', 'POST'])
@login_required
def nouvelle(candidature_id):
    candidature = Candidature.query.get_or_404(candidature_id)
    if request.method == 'POST':
        interaction = Interaction(
            candidature_id   = candidature_id,
            type_interaction = request.form['type_interaction'],
            notes            = request.form.get('notes'),
            date             = datetime.utcnow(),
        )
        db.session.add(interaction)
        db.session.commit()
        flash('Interaction enregistrée.', 'success')
        return redirect(url_for('candidatures.detail', id=candidature_id))
    return render_template('interactions/form.html',
        candidature=candidature,
        types=Interaction.TYPES,
    )


@interactions_bp.route('/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer(id):
    interaction = Interaction.query.get_or_404(id)
    candidature_id = interaction.candidature_id
    db.session.delete(interaction)
    db.session.commit()
    flash('Interaction supprimée.', 'warning')
    return redirect(url_for('candidatures.detail', id=candidature_id))
