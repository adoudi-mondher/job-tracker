from flask import Blueprint, render_template, session, redirect, url_for, request, current_app
from app.models import Candidature, Entreprise, Interaction

main_bp = Blueprint('main', __name__)


def login_required(f):
    """Décorateur simple — vérifie le mot de passe en session"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password == current_app.config['APP_PASSWORD']:
            session['authenticated'] = True
            return redirect(url_for('main.dashboard'))
        error = 'Mot de passe incorrect'
    return render_template('base/login.html', error=error)


@main_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))


@main_bp.route('/')
@login_required
def dashboard():
    # Stats globales
    total         = Candidature.query.count()
    envoyees      = Candidature.query.filter_by(statut='Envoyée').count()
    entretiens    = Candidature.query.filter_by(statut='Entretien').count()
    refus         = Candidature.query.filter_by(statut='Refus').count()

    # Candidatures avec relance due
    toutes = Candidature.query.all()
    relances_dues = [c for c in toutes if c.relance_due]

    # 5 dernières interactions
    interactions_recentes = Interaction.query.order_by(
        Interaction.date.desc()
    ).limit(5).all()

    return render_template('base/dashboard.html',
        total=total,
        envoyees=envoyees,
        entretiens=entretiens,
        refus=refus,
        relances_dues=relances_dues,
        interactions_recentes=interactions_recentes,
    )
