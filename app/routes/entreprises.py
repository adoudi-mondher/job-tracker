from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Entreprise
from app.routes.main import login_required

entreprises_bp = Blueprint('entreprises', __name__)

@entreprises_bp.route('/')
@login_required
def index():
    page    = request.args.get('page', 1, type=int)
    secteur = request.args.get('secteur')
    localisation = request.args.get('localisation')

    query = Entreprise.query.order_by(Entreprise.nom)
    if secteur:
        query = query.filter_by(secteur=secteur)
    if localisation:
        query = query.filter(Entreprise.localisation.ilike(f'%{localisation}%'))

    entreprises = query.paginate(page=page, per_page=20, error_out=False)

    # Liste des secteurs distincts pour les filtres
    secteurs = [r[0] for r in db.session.query(Entreprise.secteur)
                .filter(Entreprise.secteur.isnot(None))
                .filter(Entreprise.secteur != '')
                .distinct().order_by(Entreprise.secteur).all()]

    return render_template('entreprises/index.html',
        entreprises=entreprises,
        secteurs=secteurs,
        secteur_filtre=secteur,
        localisation_filtre=localisation,
    )

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

@entreprises_bp.route('/export')
@login_required
def export():
    import csv
    import io
    from flask import Response

    entreprises = Entreprise.query.order_by(Entreprise.nom).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Nom', 'Secteur', 'Localisation', 'Site web',
                     'Contact nom', 'Contact email', 'Notes', 'Candidatures'])
    for e in entreprises:
        writer.writerow([e.nom, e.secteur or '', e.localisation or '',
                         e.site_web or '', e.contact_nom or '',
                         e.contact_email or '', e.notes or '',
                         len(e.candidatures)])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=entreprises.csv'})