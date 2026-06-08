from datetime import datetime, timedelta
from io import BytesIO

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for

from app import db
from app.lm_template import LM_TEMPLATE
from app.models import Candidature, Entreprise
from app.routes.main import login_required
from app.webhooks import send_webhook

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

        # ── W2 : enrichissement auto si URL → W2 chainera W3 en fin de workflow
        # ── W3 : génération LM directe si pas d'URL
        if candidature.lien_offre:
            send_webhook(
                current_app.config["N8N_WEBHOOK_ENRICH"],
                {"candidature_id": candidature.id, "url": candidature.lien_offre},
            )
            flash("Candidature ajoutée. Enrichissement + lettre de motivation en cours de génération…", "info")
        else:
            send_webhook(
                current_app.config["N8N_WEBHOOK_LM"],
                {"candidature_id": candidature.id, "lm_template": LM_TEMPLATE},
            )
            flash("Candidature ajoutée. Lettre de motivation en cours de génération…", "info")

        # Redirection vers le detail pour voir l'enrichissement
        return redirect(url_for("candidatures.detail", id=candidature.id))
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
        # lettre_motivation : present dans le form rapide du detail OU dans le form complet
        if "lettre_motivation" in request.form:
            candidature.lettre_motivation = request.form.get("lettre_motivation") or None
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
    ancien_statut = candidature.statut
    nouveau_statut = request.form.get("statut")
    if nouveau_statut in Candidature.STATUTS:
        candidature.statut = nouveau_statut
        db.session.commit()

        # ── W3 : generation LM quand on passe explicitement a "A envoyer" ─────
        # On exclut la creation (ancien_statut == "A envoyer" -> pas de changement reel)
        if nouveau_statut == "À envoyer" and ancien_statut != "À envoyer":
            send_webhook(
                current_app.config["N8N_WEBHOOK_LM"],
                {"candidature_id": candidature.id, "lm_template": LM_TEMPLATE},
            )

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


# ── Export LM → PDF ───────────────────────────────────────────────────────────


@candidatures_bp.route("/<int:id>/lm.pdf")
@login_required
def export_lm_pdf(id):
    import re
    from fpdf import FPDF

    candidature = Candidature.query.get_or_404(id)
    if not candidature.lettre_motivation:
        flash("Aucune lettre de motivation disponible pour cette candidature.", "warning")
        return redirect(url_for("candidatures.detail", id=id))

    entreprise_nom = candidature.entreprise.nom if candidature.entreprise else ""
    entreprise_ville = candidature.entreprise.localisation if candidature.entreprise else ""

    def clean(text):
        """Retire le markdown et normalise les caractères hors latin-1."""
        text = re.sub(r"\*+([^*]*)\*+", r"\1", text)   # **gras** / *italique*
        text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)  # séparateurs ---
        text = text.replace("–", "-").replace("—", "-")  # tirets longs
        text = text.replace("‘", "'").replace("’", "'")  # apostrophes
        text = text.replace("“", '"').replace("”", '"')  # guillemets
        # encode/decode latin-1 : remplace ce qui reste hors portée
        return text.encode("latin-1", errors="replace").decode("latin-1")

    NL = {"new_x": "LMARGIN", "new_y": "NEXT"}

    class LM_PDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 13)
            self.cell(0, 8, "Mondher Adoudi", **NL)
            self.set_font("Helvetica", "", 9)
            self.set_text_color(80, 80, 80)
            self.cell(0, 5, "adoudi.mondher@gmail.com  |  06 67 06 61 96  |  linkedin.com/in/mondher-adoudi  |  github.com/adoudi-mondher", **NL)
            self.set_text_color(0, 0, 0)
            self.set_draw_color(180, 180, 180)
            self.line(self.l_margin, self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
            self.ln(6)

    pdf = LM_PDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(left=22, top=20, right=22)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Bloc destinataire
    pdf.set_font("Helvetica", "", 10)
    if entreprise_nom:
        pdf.cell(0, 6, clean(entreprise_nom), **NL)
    if entreprise_ville:
        pdf.cell(0, 6, clean(entreprise_ville), **NL)
    pdf.ln(3)

    # Date
    date_fr = datetime.utcnow().strftime("%d/%m/%Y")
    pdf.cell(0, 6, f"Metz, le {date_fr}", align="R", **NL)
    pdf.ln(4)

    # Objet
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, clean(f"Objet : Candidature - {candidature.poste}"), **NL)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "MSc D\xe9veloppement Informatique / IA Epitech (2 ans)", **NL)
    pdf.ln(4)

    # Corps de la lettre
    pdf.set_font("Helvetica", "", 10)
    for paragraph in candidature.lettre_motivation.split("\n"):
        para = clean(paragraph.strip())
        if para:
            pdf.multi_cell(0, 6, para)
            pdf.ln(2)
        else:
            pdf.ln(3)

    # Signature
    pdf.ln(4)
    pdf.multi_cell(0, 6, "Je suis disponible pour un \xe9change d\xe8s que vous le souhaitez.")
    pdf.ln(4)
    pdf.cell(0, 6, "Cordialement,", **NL)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Mondher Adoudi", **NL)

    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)

    safe_poste = "".join(c if c.isalnum() or c in " -_" else "_" for c in candidature.poste)
    safe_entreprise = "".join(c if c.isalnum() or c in " -_" else "_" for c in entreprise_nom)
    filename = f"LM_{safe_poste}_{safe_entreprise}.pdf".replace(" ", "_")

    return Response(
        buf.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
