from datetime import datetime, timedelta

from app import db


class Entreprise(db.Model):
    __tablename__ = "entreprise"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), nullable=False)
    secteur = db.Column(db.String(50))
    localisation = db.Column(db.String(100))
    site_web = db.Column(db.String(255))
    contact_nom = db.Column(db.String(100))
    contact_email = db.Column(db.String(150))
    notes = db.Column(db.Text)

    candidatures = db.relationship(
        "Candidature", backref="entreprise", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Entreprise {self.nom}>"

    def to_dict(self):
        return {
            "id": self.id,
            "nom": self.nom,
            "secteur": self.secteur,
            "localisation": self.localisation,
            "site_web": self.site_web,
            "contact_nom": self.contact_nom,
            "contact_email": self.contact_email,
        }


class Candidature(db.Model):
    __tablename__ = "candidature"

    STATUTS = ["À envoyer", "Envoyée", "Relance", "Entretien", "Refus", "Abandonné"]
    TYPES_CONTRAT = ["Stage", "Alternance", "CDI", "CDD"]

    id = db.Column(db.Integer, primary_key=True)
    entreprise_id = db.Column(
        db.Integer, db.ForeignKey("entreprise.id"), nullable=False
    )
    poste = db.Column(db.String(200), nullable=False)
    type_contrat = db.Column(db.String(20), default="Alternance")
    date_envoi = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    statut = db.Column(db.String(20), default="À envoyer")
    lien_offre = db.Column(db.String(2000))
    lm_fichier = db.Column(db.String(255))
    date_relance = db.Column(db.Date)
    date_modification = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    notes = db.Column(db.Text)

    # ── Soft delete / archivage ───────────────────────────────────────────────
    # NULL  → candidature active
    # datetime → archivée (campagne clôturée)
    archived_at = db.Column(db.DateTime, nullable=True, default=None)
    # ─────────────────────────────────────────────────────────────────────────

    # ── Champs n8n / enrichissement automatique ──────────────────────────────
    # source : "manual" (saisie UI), "auto" (scraping n8n), "lba" (La Bonne Alternance)
    source = db.Column(db.String(50), default="manual", nullable=False)
    # Enrichissement W2 (extraction depuis URL de l'offre via Claude)
    stack_technique = db.Column(db.Text, nullable=True)
    resume_offre = db.Column(db.Text, nullable=True)
    # Lettre de motivation W3 (brouillon généré par Claude)
    lettre_motivation = db.Column(db.Text, nullable=True)
    # Message email d'accompagnement (rédigé manuellement pour envoi direct par email)
    message_accompagnement = db.Column(db.Text, nullable=True)
    # Préparation entretien (pitch, hard/soft skills, transposition stack) générée par le Rédacteur
    prep_entretien = db.Column(db.Text, nullable=True)
    # ─────────────────────────────────────────────────────────────────────────

    interactions = db.relationship(
        "Interaction", backref="candidature", lazy=True, cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.date_envoi and not self.date_relance:
            self.date_relance = self.date_envoi + timedelta(days=7)

    @property
    def is_archived(self):
        return self.archived_at is not None

    @property
    def jours_depuis_envoi(self):
        if self.date_envoi:
            return (datetime.utcnow().date() - self.date_envoi).days
        return None

    @property
    def relance_due(self):
        if self.date_relance and self.statut == "Envoyée":
            return datetime.utcnow().date() >= self.date_relance
        return False

    def __repr__(self):
        return f"<Candidature {self.poste} @ {self.entreprise_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "entreprise_id": self.entreprise_id,
            "entreprise_nom": self.entreprise.nom if self.entreprise else None,
            "poste": self.poste,
            "type_contrat": self.type_contrat,
            "date_envoi": self.date_envoi.isoformat() if self.date_envoi else None,
            "statut": self.statut,
            "lien_offre": self.lien_offre,
            "lm_fichier": self.lm_fichier,
            "date_relance": self.date_relance.isoformat()
            if self.date_relance
            else None,
            "date_modification": self.date_modification.isoformat()
            if self.date_modification
            else None,
            "notes": self.notes,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "jours_depuis_envoi": self.jours_depuis_envoi,
            "relance_due": self.relance_due,
            "source": self.source,
            "stack_technique": self.stack_technique,
            "resume_offre": self.resume_offre,
            "lettre_motivation": self.lettre_motivation,
            "message_accompagnement": self.message_accompagnement,
            "prep_entretien": self.prep_entretien,
        }


class Interaction(db.Model):
    __tablename__ = "interaction"

    TYPES = ["Email envoyé", "Email reçu", "Appel", "Entretien", "Relance", "Note"]

    id = db.Column(db.Integer, primary_key=True)
    candidature_id = db.Column(
        db.Integer, db.ForeignKey("candidature.id"), nullable=False
    )
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    type_interaction = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text)

    def __repr__(self):
        return f"<Interaction {self.type_interaction} - {self.date}>"

    def to_dict(self):
        return {
            "id": self.id,
            "candidature_id": self.candidature_id,
            "date": self.date.isoformat(),
            "type_interaction": self.type_interaction,
            "notes": self.notes,
        }
