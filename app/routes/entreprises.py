from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Entreprise
from app.routes.main import login_required

entreprises_bp = Blueprint('entreprises', __name__)


@entreprises_bp.route('/')
@login_required
def index():
    entreprises = Entreprise.query.order_by(Entreprise.nom).all()
    return render_template('entreprises/index.html', entreprises=entreprises)


@entreprises_bp.route('/nouvelle', methods=['GET', 'POST'])
@login_required
def nouvelle():
    if request.method == 'POST':
        entreprise = Entreprise(
            nom           = request.form['nom'],
            secteur       = request.form.get('secteur'),
            localisation  = request.form.get('localisation'),
            site_web      = request.form.get('site_web'),
            contact_nom   = request.form.get('contact_nom'),
            contact_email = request.form.get('contact_email'),
        )
        db.session.add(entreprise)
        db.session.commit()
        flash(f'Entreprise "{entreprise.nom}" ajoutée.', 'success')
        return redirect(url_for('entreprises.index'))
    return render_template('entreprises/form.html', entreprise=None)


@entreprises_bp.route('/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier(id):
    entreprise = Entreprise.query.get_or_404(id)
    if request.method == 'POST':
        entreprise.nom           = request.form['nom']
        entreprise.secteur       = request.form.get('secteur')
        entreprise.localisation  = request.form.get('localisation')
        entreprise.site_web      = request.form.get('site_web')
        entreprise.contact_nom   = request.form.get('contact_nom')
        entreprise.contact_email = request.form.get('contact_email')
        db.session.commit()
        flash(f'Entreprise "{entreprise.nom}" mise à jour.', 'success')
        return redirect(url_for('entreprises.index'))
    return render_template('entreprises/form.html', entreprise=entreprise)


@entreprises_bp.route('/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer(id):
    entreprise = Entreprise.query.get_or_404(id)
    db.session.delete(entreprise)
    db.session.commit()
    flash(f'Entreprise "{entreprise.nom}" supprimée.', 'warning')
    return redirect(url_for('entreprises.index'))
