from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import db
from app.models import Candidature, Entreprise
from app.routes.main import login_required

candidatures_bp = Blueprint("candidatures", __name__)


# ── Liste ─────────────────────────────────────────────────────────────────────


@candidatures_bp.route("/")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    statut = request.args.get("statut")
    archives = request.args.get("archives", "0") == "1"

    query = Candidature.query.order_by(Candidature.date_envoi.desc())

    # Vue par défaut : actives seulement — archives sur ?archives=1
    if archives:
        query = query.filter(Candidature.archived_at.isnot(None))
    else:
        query = query.filter(Candidature.archived_at.is_(None))

    if statut:
        query = query.filter_by(statut=statut)

    candidatures = query.paginate(page=page, per_page=20, error_out=False)

    return render_template(
        "candidatures/index.html",
        candidatures=candidatures,
        statuts=Candidature.STATUTS,
        statut_filtre=statut,
        archives=archives,
    )


# ── Détail ────────────────────────────────────────────────────────────────────


@candidatures_bp.route("/<int:id>")
@login_required
def detail(id):
    candidature = Candidature.query.get_or_404(id)
    return render_template(
        "candidatures/detail.html",
        candidature=candidature,
        statuts=Candidature.STATUTS,
    )


# ── Création ──────────────────────────────────────────────────────────────────


@candidatures_bp.route("/nouvelle", methods=["GET", "POST"])
@login_required
def nouvelle():
    entreprises = Entreprise.query.order_by(Entreprise.nom).all()
    if request.method == "POST":
        date_envoi = datetime.strptime(request.form["date_envoi"], "%Y-%m-%d").date()
        candidature = Candidature(
            entreprise_id=request.form["entreprise_id"],
            poste=request.form["poste"],
            type_contrat=request.form.get("type_contrat", "Alternance"),
            date_envoi=date_envoi,
            statut=request.form.get("statut", "À envoyer"),
            lien_offre=request.form.get("lien_offre"),
            lm_fichier=request.form.get("lm_fichier"),
            date_relance=date_envoi + timedelta(days=7),
            notes=request.form.get("notes"),
        )
        db.session.add(candidature)
        db.session.commit()
        flash("Candidature ajoutée.", "success")
        return redirect(url_for("candidatures.index"))
    return render_template(
        "candidatures/form.html",
        candidature=None,
        entreprises=entreprises,
        statuts=Candidature.STATUTS,
        types_contrat=Candidature.TYPES_CONTRAT,
        today=datetime.utcnow().strftime("%Y-%m-%d"),
    )


# ── Modification ──────────────────────────────────────────────────────────────


@candidatures_bp.route("/<int:id>/modifier", methods=["GET", "POST"])
@login_required
def modifier(id):
    candidature = Candidature.query.get_or_404(id)
    entreprises = Entreprise.query.order_by(Entreprise.nom).all()
    if request.method == "POST":
        candidature.entreprise_id = request.form["entreprise_id"]
        candidature.poste = request.form["poste"]
        candidature.type_contrat = request.form.get("type_contrat")
        candidature.date_envoi = datetime.strptime(
            request.form["date_envoi"], "%Y-%m-%d"
        ).date()
        candidature.statut = request.form.get("statut")
        candidature.lien_offre = request.form.get("lien_offre")
        candidature.lm_fichier = request.form.get("lm_fichier")
        candidature.notes = request.form.get("notes")
        db.session.commit()
        flash("Candidature mise à jour.", "success")
        return redirect(url_for("candidatures.detail", id=candidature.id))
    return render_template(
        "candidatures/form.html",
        candidature=candidature,
        entreprises=entreprises,
        statuts=Candidature.STATUTS,
        types_contrat=Candidature.TYPES_CONTRAT,
        today=datetime.utcnow().strftime("%Y-%m-%d"),
    )


# ── Statut HTMX ───────────────────────────────────────────────────────────────


@candidatures_bp.route("/<int:id>/statut", methods=["POST"])
@login_required
def changer_statut(id):
    candidature = Candidature.query.get_or_404(id)
    nouveau_statut = request.form.get("statut")
    if nouveau_statut in Candidature.STATUTS:
        candidature.statut = nouveau_statut
        db.session.commit()
    return render_template(
        "candidatures/_statut_badge.html",
        candidature=candidature,
        statuts=Candidature.STATUTS,
    )


# ── Archivage ─────────────────────────────────────────────────────────────────


@candidatures_bp.route("/<int:id>/archiver", methods=["POST"])
@login_required
def archiver(id):
    """Archive une candidature individuelle (soft delete)."""
    candidature = Candidature.query.get_or_404(id)
    candidature.archived_at = datetime.utcnow()
    db.session.commit()
    flash(f"Candidature archivée.", "success")
    return redirect(url_for("candidatures.index"))


@candidatures_bp.route("/<int:id>/desarchiver", methods=["POST"])
@login_required
def desarchiver(id):
    """Restaure une candidature archivée."""
    candidature = Candidature.query.get_or_404(id)
    candidature.archived_at = None
    db.session.commit()
    flash("Candidature restaurée dans les actives.", "success")
    return redirect(url_for("candidatures.index", archives=1))


@candidatures_bp.route("/archiver-tout", methods=["POST"])
@login_required
def archiver_tout():
    """Clôture toute la campagne active — archive en masse."""
    now = datetime.utcnow()
    count = Candidature.query.filter(Candidature.archived_at.is_(None)).update(
        {"archived_at": now}
    )
    db.session.commit()
    flash(f"{count} candidature(s) archivée(s). Nouvelle campagne prête.", "success")
    return redirect(url_for("candidatures.index"))


# ── Suppression définitive ────────────────────────────────────────────────────


@candidatures_bp.route("/<int:id>/supprimer", methods=["POST"])
@login_required
def supprimer(id):
    candidature = Candidature.query.get_or_404(id)
    db.session.delete(candidature)
    db.session.commit()
    flash("Candidature supprimée définitivement.", "warning")
    return redirect(url_for("candidatures.index"))


# ── Export CSV ────────────────────────────────────────────────────────────────


@candidatures_bp.route("/export")
@login_required
def export():
    import csv
    import io

    from flask import Response

    archives = request.args.get("archives", "0") == "1"
    query = Candidature.query.order_by(Candidature.date_envoi.desc())
    if archives:
        query = query.filter(Candidature.archived_at.isnot(None))
    else:
        query = query.filter(Candidature.archived_at.is_(None))

    candidatures = query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Entreprise",
            "Secteur",
            "Localisation",
            "Poste",
            "Type contrat",
            "Date envoi",
            "Statut",
            "Date relance",
            "Lien offre",
            "Fichier LM",
            "Notes",
            "Archivée le",
        ]
    )
    for c in candidatures:
        writer.writerow(
            [
                c.entreprise.nom if c.entreprise else "",
                c.entreprise.secteur if c.entreprise else "",
                c.entreprise.localisation if c.entreprise else "",
                c.poste,
                c.type_contrat or "",
                c.date_envoi.strftime("%d/%m/%Y") if c.date_envoi else "",
                c.statut or "",
                c.date_relance.strftime("%d/%m/%Y") if c.date_relance else "",
                c.lien_offre or "",
                c.lm_fichier or "",
                c.notes or "",
                c.archived_at.strftime("%d/%m/%Y") if c.archived_at else "",
            ]
        )
    output.seek(0)
    filename = "candidatures_archives.csv" if archives else "candidatures.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
