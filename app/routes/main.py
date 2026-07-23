from collections import Counter
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.orm import joinedload

from app.models import Candidature, Entreprise, Interaction

main_bp = Blueprint("main", __name__)


def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)

    return decorated


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = request.form.get("password")
        if password == current_app.config["APP_PASSWORD"]:
            session["authenticated"] = True
            return redirect(url_for("main.dashboard"))
        error = "Mot de passe incorrect"
    return render_template("base/login.html", error=error)


@main_bp.route("/rapport")
def rapport():
    toutes = (
        Candidature.query
        .filter(Candidature.archived_at.is_(None))
        .options(joinedload(Candidature.interactions))
        .order_by(Candidature.date_envoi.desc())
        .all()
    )

    stats = Counter(c.statut for c in toutes)

    entretiens_refuses = [
        c for c in toutes
        if c.statut == "Refus"
        and any(i.type_interaction == "Entretien" for i in c.interactions)
    ]

    return render_template(
        "base/rapport.html",
        candidatures=toutes,
        stats=stats,
        entretiens_refuses=entretiens_refuses,
        date_rapport=datetime.utcnow().strftime("%d/%m/%Y"),
    )


@main_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@main_bp.route("/")
@login_required
def dashboard():
    # Dashboard : candidatures actives uniquement (non archivées)
    toutes = Candidature.query.filter(Candidature.archived_at.is_(None)).all()

    # Stats globales
    total = len(toutes)
    envoyees = sum(1 for c in toutes if c.statut == "Envoyée")
    entretiens = sum(1 for c in toutes if c.statut == "Entretien")
    refus = sum(1 for c in toutes if c.statut == "Refus")

    # Relances dues (actives uniquement)
    relances_dues = [c for c in toutes if c.relance_due]

    # 5 dernières interactions (toutes campagnes confondues)
    interactions_recentes = (
        Interaction.query.order_by(Interaction.date.desc()).limit(5).all()
    )

    # --- Données graphiques ---

    # Donut : répartition par statut (actives)
    statuts_ordre = [
        "À envoyer",
        "Envoyée",
        "Relance",
        "Entretien",
        "Refus",
        "Abandonné",
    ]
    statuts_count = Counter(c.statut for c in toutes)
    donut_labels = statuts_ordre
    donut_data = [statuts_count.get(s, 0) for s in statuts_ordre]
    donut_colors = ["#adb5bd", "#3b5bdb", "#f59f00", "#2f9e44", "#e03131", "#868e96"]

    # Bar : candidatures actives par semaine (8 dernières semaines)
    aujourd_hui = datetime.utcnow().date()
    semaines_labels = []
    semaines_data = []
    for i in range(7, -1, -1):
        debut = aujourd_hui - timedelta(weeks=i + 1)
        fin = aujourd_hui - timedelta(weeks=i)
        label = debut.strftime("S%W")
        count = sum(1 for c in toutes if c.date_envoi and debut <= c.date_envoi < fin)
        semaines_labels.append(label)
        semaines_data.append(count)

    # Compteur archives pour le dashboard
    nb_archivees = Candidature.query.filter(Candidature.archived_at.isnot(None)).count()

    return render_template(
        "base/dashboard.html",
        total=total,
        envoyees=envoyees,
        entretiens=entretiens,
        refus=refus,
        relances_dues=relances_dues,
        interactions_recentes=interactions_recentes,
        donut_labels=donut_labels,
        donut_data=donut_data,
        donut_colors=donut_colors,
        semaines_labels=semaines_labels,
        semaines_data=semaines_data,
        nb_archivees=nb_archivees,
    )
