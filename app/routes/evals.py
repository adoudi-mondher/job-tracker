from collections import Counter, defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, render_template
from sqlalchemy.exc import OperationalError, ProgrammingError

from app import db
from app.models import LlmCall, LmGenerationRun
from app.routes.main import login_required

evals_bp = Blueprint("evals", __name__)


@evals_bp.route("/")
@login_required
def index():
    try:
        appels = LlmCall.query.order_by(LlmCall.created_at.desc()).all()
        runs = LmGenerationRun.query.order_by(LmGenerationRun.created_at.desc()).all()
    except (OperationalError, ProgrammingError):
        # Tables gérées par langgraph-agents (ensure_table) — absentes en dev local (sqlite)
        # ou si le service n'a jamais tourné contre cette base.
        db.session.rollback()
        appels, runs = [], []

    aujourd_hui = datetime.utcnow().date()
    debut_semaine = aujourd_hui - timedelta(days=7)

    cout_total = sum(float(a.cost_usd or 0) for a in appels)
    cout_semaine = sum(
        float(a.cost_usd or 0) for a in appels if a.created_at and a.created_at.date() >= debut_semaine
    )
    cout_jour = sum(
        float(a.cost_usd or 0) for a in appels if a.created_at and a.created_at.date() == aujourd_hui
    )

    cout_par_node = defaultdict(float)
    tokens_par_node = defaultdict(lambda: {"input": 0, "output": 0})
    for a in appels:
        cout_par_node[a.node] += float(a.cost_usd or 0)
        tokens_par_node[a.node]["input"] += a.input_tokens or 0
        tokens_par_node[a.node]["output"] += a.output_tokens or 0

    nb_runs = len(runs)
    nb_conformes = sum(1 for r in runs if r.statut_verification == "conforme")
    nb_premier_coup = sum(
        1 for r in runs if r.statut_verification == "conforme" and r.nb_iterations == 1
    )
    taux_conforme = (nb_conformes / nb_runs * 100) if nb_runs else 0
    taux_premier_coup = (nb_premier_coup / nb_runs * 100) if nb_runs else 0

    motifs_compteur = Counter()
    for r in runs:
        for motif in (r.motifs_json or []):
            motifs_compteur[motif] += 1
    top_motifs = motifs_compteur.most_common(5)

    return render_template(
        "evals/index.html",
        cout_total=cout_total,
        cout_semaine=cout_semaine,
        cout_jour=cout_jour,
        nb_appels=len(appels),
        cout_par_node=sorted(cout_par_node.items(), key=lambda x: x[1], reverse=True),
        tokens_par_node=tokens_par_node,
        nb_runs=nb_runs,
        taux_conforme=taux_conforme,
        taux_premier_coup=taux_premier_coup,
        top_motifs=top_motifs,
        runs_recents=runs[:10],
    )
