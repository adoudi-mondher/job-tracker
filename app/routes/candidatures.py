from datetime import datetime, timedelta
from io import BytesIO

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for

from app import db
from app.models import Candidature, Entreprise, Interaction
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
            lien_offre=request.form.get("lien_offre") or None,
            lm_fichier=request.form.get("lm_fichier"),
            date_relance=date_envoi + timedelta(days=7),
            notes=request.form.get("notes"),
            resume_offre=request.form.get("resume_offre") or None,
        )
        db.session.add(candidature)
        db.session.commit()

        send_webhook(
            current_app.config["LM_AGENT_URL"],
            {
                "candidature_id": candidature.id,
                "poste": candidature.poste,
                "entreprise_nom": candidature.entreprise.nom,
                "secteur": candidature.entreprise.secteur or "",
                "resume_offre": candidature.resume_offre or "",
                "stack_technique": "",
            },
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
        candidature.lien_offre = request.form.get("lien_offre") or None
        candidature.resume_offre = request.form.get("resume_offre") or None
        candidature.lm_fichier = request.form.get("lm_fichier")
        candidature.notes = request.form.get("notes")
        # lettre_motivation : present dans le form rapide du detail OU dans le form complet
        if "lettre_motivation" in request.form:
            candidature.lettre_motivation = request.form.get("lettre_motivation") or None
        if "message_accompagnement" in request.form:
            candidature.message_accompagnement = request.form.get("message_accompagnement") or None
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

        if nouveau_statut == "Entretien" and ancien_statut != "Entretien":
            db.session.add(Interaction(
                candidature_id=candidature.id,
                type_interaction="Entretien",
                notes="Entretien enregistré automatiquement lors du changement de statut.",
            ))

        db.session.commit()

        # ── W3 : generation LM quand on passe explicitement a "A envoyer" ─────
        # On exclut la creation (ancien_statut == "A envoyer" -> pas de changement reel)
        if nouveau_statut == "À envoyer" and ancien_statut != "À envoyer":
            send_webhook(
                current_app.config["LM_AGENT_URL"],
                {
                    "candidature_id": candidature.id,
                    "poste": candidature.poste,
                    "entreprise_nom": candidature.entreprise.nom,
                    "secteur": candidature.entreprise.secteur or "",
                    "resume_offre": candidature.resume_offre or "",
                    "stack_technique": candidature.stack_technique or "",
                },
            )

    return render_template(
        "candidatures/_statut_badge.html",
        candidature=candidature,
        statuts=Candidature.STATUTS,
    )


# ── Préparation entretien ───────────────────────────────────────────────────────


@candidatures_bp.route("/<int:id>/preparer-entretien", methods=["POST"])
@login_required
def preparer_entretien(id):
    """Déclenche la génération d'une préparation d'entretien via le Rédacteur LangGraph."""
    candidature = Candidature.query.get_or_404(id)

    send_webhook(
        current_app.config["INTERVIEW_PREP_AGENT_URL"],
        {
            "candidature_id": candidature.id,
            "poste": candidature.poste,
            "entreprise_nom": candidature.entreprise.nom,
            "secteur": candidature.entreprise.secteur or "",
            "resume_offre": candidature.resume_offre or "",
            "stack_technique": candidature.stack_technique or "",
            "notes": candidature.notes or "",
        },
    )

    flash("Préparation d'entretien en cours de génération…", "success")
    return redirect(url_for("candidatures.detail", id=candidature.id))


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


# ── Export Offre → PDF ────────────────────────────────────────────────────────


@candidatures_bp.route("/<int:id>/offre.pdf")
@login_required
def export_offre_pdf(id):
    from fpdf import FPDF

    candidature = Candidature.query.get_or_404(id)
    if not candidature.resume_offre:
        flash("Aucun texte d'offre disponible pour cette candidature.", "warning")
        return redirect(url_for("candidatures.detail", id=id))

    entreprise_nom = candidature.entreprise.nom if candidature.entreprise else ""

    def clean(text):
        text = text.replace("–", "-").replace("—", "-")
        text = text.replace("‘", "'").replace("’", "'")
        text = text.replace("“", '"').replace("”", '"')
        return text.encode("latin-1", errors="replace").decode("latin-1")

    NL = {"new_x": "LMARGIN", "new_y": "NEXT"}

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(left=22, top=20, right=22)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, clean(f"{candidature.poste}"), **NL)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, clean(entreprise_nom), **NL)
    pdf.set_text_color(0, 0, 0)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(pdf.l_margin, pdf.get_y() + 3, pdf.w - pdf.r_margin, pdf.get_y() + 3)
    pdf.ln(8)

    import textwrap
    text_w = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font("Helvetica", "", 10)
    for line in candidature.resume_offre.splitlines():
        cleaned = clean(line.strip())
        if cleaned:
            for fragment in textwrap.wrap(cleaned, width=90, break_long_words=True, break_on_hyphens=True):
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(text_w, 5.5, fragment)
        else:
            pdf.ln(3)

    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)

    safe_poste = "".join(c if c.isalnum() or c in " -_" else "_" for c in candidature.poste)
    safe_entreprise = "".join(c if c.isalnum() or c in " -_" else "_" for c in entreprise_nom)
    filename = f"Offre_{safe_poste}_{safe_entreprise}.pdf".replace(" ", "_")

    return Response(
        buf.getvalue(),
        mimetype="application/pdf",
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

    # Bloc destinataire — aligné à droite
    pdf.set_font("Helvetica", "", 10)
    if entreprise_nom:
        pdf.cell(0, 6, clean(entreprise_nom), align="R", **NL)
    if entreprise_ville:
        pdf.cell(0, 6, clean(entreprise_ville), align="R", **NL)
    pdf.ln(3)

    # Date — alignée à droite
    date_fr = datetime.utcnow().strftime("%d/%m/%Y")
    pdf.cell(0, 6, f"Le {date_fr}", align="R", **NL)
    pdf.ln(4)

    # Objet — aligné à gauche, gras
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, clean(f"Objet : Candidature - {candidature.poste}"), **NL)
    pdf.ln(6)

    # Corps — nettoyage robuste du header que Claude inclut parfois
    lm_text = candidature.lettre_motivation

    # 1. Chercher "Madame" comme point de départ idéal
    for marker in ["Madame, Monsieur,", "Madame, Monsieur", "Madame,\nMonsieur"]:
        idx = lm_text.find(marker)
        if idx > 0:
            lm_text = lm_text[idx:]
            break
    else:
        # 2. Sinon : strip ligne par ligne les patterns d'en-tête connus
        lines = lm_text.split("\n")
        header_patterns = re.compile(
            r'^(Mondher Adoudi|adoudi[@]|adoudi\.mondher|'
            r'\+33|06 67|linkedin\.com|github\.com|'
            r'Objet\s*:|Metz,|Le \d|[A-Z][a-z]+, le ).*$',
            re.IGNORECASE
        )
        start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not header_patterns.match(stripped) and len(stripped) > 40:
                start = i
                break
        lm_text = "\n".join(lines[start:])

    # 3. Strip phrase(s) de clôture et signature — tout est géré par le PDF
    cloture_patterns = [
        r"Je serais disponible pour [^\n]+\.",
        r"Je suis disponible pour [^\n]+\.",
        r"Dans l.attente[^\n]+\.",
        r"N.h[eé]sitez pas[^\n]+\.",
    ]
    for pat in cloture_patterns:
        lm_text = re.sub(pat, "", lm_text)

    for closing in ["Cordialement,", "Cordialement,"]:
        idx = lm_text.rfind(closing)
        if idx != -1:
            lm_text = lm_text[:idx].rstrip()
            break

    pdf.set_font("Helvetica", "", 10)
    for paragraph in lm_text.split("\n"):
        para = clean(paragraph.strip())
        if para:
            pdf.multi_cell(0, 6, para)
            pdf.ln(2)
        else:
            pdf.ln(3)

    # Phrase de clôture fixe
    pdf.ln(2)
    pdf.multi_cell(0, 6, "Je serais disponible pour \xe9changer sur la mani\xe8re dont mon profil peut s'int\xe9grer \xe0 vos \xe9quipes.")
    pdf.ln(6)

    # Signature
    pdf.cell(0, 6, "Cordialement,", **NL)
    pdf.ln(2)
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
