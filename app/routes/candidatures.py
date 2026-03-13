from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
from app import db
from app.models import Candidature, Entreprise
from app.routes.main import login_required

candidatures_bp = Blueprint('candidatures', __name__)


@candidatures_bp.route('/')
@login_required
def index():
    statut = request.args.get('statut')
    if statut:
        candidatures = Candidature.query.filter_by(statut=statut).order_by(
            Candidature.date_envoi.desc()).all()
    else:
        candidatures = Candidature.query.order_by(Candidature.date_envoi.desc()).all()
    return render_template('candidatures/index.html',
        candidatures=candidatures,
        statuts=Candidature.STATUTS,
        statut_filtre=statut,
    )


@candidatures_bp.route('/<int:id>')
@login_required
def detail(id):
    candidature = Candidature.query.get_or_404(id)
    return render_template('candidatures/detail.html',
        candidature=candidature,
        statuts=Candidature.STATUTS,
    )


@candidatures_bp.route('/nouvelle', methods=['GET', 'POST'])
@login_required
def nouvelle():
    entreprises = Entreprise.query.order_by(Entreprise.nom).all()
    if request.method == 'POST':
        date_envoi = datetime.strptime(request.form['date_envoi'], '%Y-%m-%d').date()
        candidature = Candidature(
            entreprise_id = request.form['entreprise_id'],
            poste         = request.form['poste'],
            type_contrat  = request.form.get('type_contrat', 'Alternance'),
            date_envoi    = date_envoi,
            statut        = request.form.get('statut', 'À envoyer'),
            lien_offre    = request.form.get('lien_offre'),
            lm_fichier    = request.form.get('lm_fichier'),
            date_relance  = date_envoi + timedelta(days=7),
            notes         = request.form.get('notes'),
        )
        db.session.add(candidature)
        db.session.commit()
        flash('Candidature ajoutée.', 'success')
        return redirect(url_for('candidatures.index'))
    return render_template('candidatures/form.html',
        candidature=None,
        entreprises=entreprises,
        statuts=Candidature.STATUTS,
        types_contrat=Candidature.TYPES_CONTRAT,
        today=datetime.utcnow().strftime('%Y-%m-%d'),
    )


@candidatures_bp.route('/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier(id):
    candidature = Candidature.query.get_or_404(id)
    entreprises = Entreprise.query.order_by(Entreprise.nom).all()
    if request.method == 'POST':
        candidature.entreprise_id = request.form['entreprise_id']
        candidature.poste         = request.form['poste']
        candidature.type_contrat  = request.form.get('type_contrat')
        candidature.date_envoi    = datetime.strptime(request.form['date_envoi'], '%Y-%m-%d').date()
        candidature.statut        = request.form.get('statut')
        candidature.lien_offre    = request.form.get('lien_offre')
        candidature.lm_fichier    = request.form.get('lm_fichier')
        candidature.notes         = request.form.get('notes')
        db.session.commit()
        flash('Candidature mise à jour.', 'success')
        return redirect(url_for('candidatures.detail', id=candidature.id))
    return render_template('candidatures/form.html',
        candidature=candidature,
        entreprises=entreprises,
        statuts=Candidature.STATUTS,
        types_contrat=Candidature.TYPES_CONTRAT,
        today=datetime.utcnow().strftime('%Y-%m-%d'),
    )


@candidatures_bp.route('/<int:id>/statut', methods=['POST'])
@login_required
def changer_statut(id):
    """Endpoint HTMX — change le statut sans recharger la page"""
    candidature = Candidature.query.get_or_404(id)
    nouveau_statut = request.form.get('statut')
    if nouveau_statut in Candidature.STATUTS:
        candidature.statut = nouveau_statut
        db.session.commit()
    return render_template('candidatures/_statut_badge.html',
        candidature=candidature,
        statuts=Candidature.STATUTS,
    )


@candidatures_bp.route('/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer(id):
    candidature = Candidature.query.get_or_404(id)
    db.session.delete(candidature)
    db.session.commit()
    flash('Candidature supprimée.', 'warning')
    return redirect(url_for('candidatures.index'))
