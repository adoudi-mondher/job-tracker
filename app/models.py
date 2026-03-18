from datetime import datetime, timedelta
from app import db


class Entreprise(db.Model):
    __tablename__ = 'entreprise'

    id            = db.Column(db.Integer, primary_key=True)
    nom           = db.Column(db.String(150), nullable=False)
    secteur       = db.Column(db.String(50))   # Énergie / BTP / Industrie / Startup / Autre
    localisation  = db.Column(db.String(100))
    site_web      = db.Column(db.String(255))
    contact_nom   = db.Column(db.String(100))
    contact_email = db.Column(db.String(150))

    # Relation : une entreprise → plusieurs candidatures
    candidatures  = db.relationship('Candidature', backref='entreprise', lazy=True,
                                    cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Entreprise {self.nom}>'

    def to_dict(self):
        return {
            'id':            self.id,
            'nom':           self.nom,
            'secteur':       self.secteur,
            'localisation':  self.localisation,
            'site_web':      self.site_web,
            'contact_nom':   self.contact_nom,
            'contact_email': self.contact_email,
        }


class Candidature(db.Model):
    __tablename__ = 'candidature'

    STATUTS = ['À envoyer', 'Envoyée', 'Relance', 'Entretien', 'Refus', 'Abandonné']
    TYPES_CONTRAT = ['Stage', 'Alternance', 'CDI', 'CDD']

    id                = db.Column(db.Integer, primary_key=True)
    entreprise_id     = db.Column(db.Integer, db.ForeignKey('entreprise.id'), nullable=False)
    poste             = db.Column(db.String(200), nullable=False)
    type_contrat      = db.Column(db.String(20), default='Alternance')
    date_envoi        = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    statut            = db.Column(db.String(20), default='À envoyer')
    lien_offre        = db.Column(db.String(2000))
    lm_fichier        = db.Column(db.String(255))  # nom du fichier PDF LM
    date_relance      = db.Column(db.Date)          # calculée auto ou saisie
    date_modification = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes             = db.Column(db.Text)

    # Relation : une candidature → plusieurs interactions
    interactions      = db.relationship('Interaction', backref='candidature', lazy=True,
                                        cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Calcul automatique date de relance = date_envoi + 7 jours
        if self.date_envoi and not self.date_relance:
            self.date_relance = self.date_envoi + timedelta(days=7)

    @property
    def jours_depuis_envoi(self):
        if self.date_envoi:
            return (datetime.utcnow().date() - self.date_envoi).days
        return None

    @property
    def relance_due(self):
        """Retourne True si la relance est due et statut toujours 'Envoyée'"""
        if self.date_relance and self.statut == 'Envoyée':
            return datetime.utcnow().date() >= self.date_relance
        return False

    def __repr__(self):
        return f'<Candidature {self.poste} @ {self.entreprise_id}>'

    def to_dict(self):
        return {
            'id':                self.id,
            'entreprise_id':     self.entreprise_id,
            'entreprise_nom':    self.entreprise.nom if self.entreprise else None,
            'poste':             self.poste,
            'type_contrat':      self.type_contrat,
            'date_envoi':        self.date_envoi.isoformat() if self.date_envoi else None,
            'statut':            self.statut,
            'lien_offre':        self.lien_offre,
            'lm_fichier':        self.lm_fichier,
            'date_relance':      self.date_relance.isoformat() if self.date_relance else None,
            'date_modification': self.date_modification.isoformat() if self.date_modification else None,
            'notes':             self.notes,
            'jours_depuis_envoi': self.jours_depuis_envoi,
            'relance_due':       self.relance_due,
        }


class Interaction(db.Model):
    __tablename__ = 'interaction'

    TYPES = ['Email envoyé', 'Email reçu', 'Appel', 'Entretien', 'Relance', 'Note']

    id               = db.Column(db.Integer, primary_key=True)
    candidature_id   = db.Column(db.Integer, db.ForeignKey('candidature.id'), nullable=False)
    date             = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    type_interaction = db.Column(db.String(30), nullable=False)
    notes            = db.Column(db.Text)

    def __repr__(self):
        return f'<Interaction {self.type_interaction} - {self.date}>'

    def to_dict(self):
        return {
            'id':               self.id,
            'candidature_id':   self.candidature_id,
            'date':             self.date.isoformat(),
            'type_interaction': self.type_interaction,
            'notes':            self.notes,
        }
