import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Entreprise, Candidature
from app.routes.main import login_required
from config import Config
from datetime import datetime, timedelta

offres_bp = Blueprint('offres', __name__)

LBA_API_URL = "https://api.apprentissage.beta.gouv.fr/api/job/v1/search"
DEFAULT_PARAMS = {
    "latitude": 49.1193,
    "longitude": 6.1757,
    "radius": 30,
    "target_diploma_level": "3",
    "romes": "M1806,M1803,M1805",
}


def fetch_offres(params):
    """Appel API LBA — retourne (jobs, recruiters) ou ([], []) en cas d'erreur"""
    try:
        resp = requests.get(
            LBA_API_URL,
            params=params,
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {Config.LBA_API_KEY}",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("jobs", []), data.get("recruiters", [])
    except Exception as e:
        return [], []


@offres_bp.route("/")
@login_required
def index():
    params = {
        "latitude":             request.args.get("latitude",  DEFAULT_PARAMS["latitude"]),
        "longitude":            request.args.get("longitude", DEFAULT_PARAMS["longitude"]),
        "radius":               request.args.get("radius",    DEFAULT_PARAMS["radius"]),
        "target_diploma_level": request.args.get("diploma",   DEFAULT_PARAMS["target_diploma_level"]),
        "romes":                request.args.get("romes",     DEFAULT_PARAMS["romes"]),
    }
    jobs, recruiters = fetch_offres(params)
    return render_template("offres/index.html",
        jobs=jobs,
        recruiters=recruiters,
        params=params,
        default=DEFAULT_PARAMS,
    )


@offres_bp.route("/ajouter", methods=["POST"])
@login_required
def ajouter():
    """Crée entreprise + candidature spontanée depuis un recruteur LBA"""
    nom         = request.form.get("nom")
    localisation = request.form.get("localisation")
    site_web    = request.form.get("site_web") or None
    lien_offre  = request.form.get("lien_offre") or None
    naf_label   = request.form.get("naf_label") or None

    # Créer ou récupérer l'entreprise
    entreprise = Entreprise.query.filter_by(nom=nom).first()
    if not entreprise:
        entreprise = Entreprise(
            nom=nom,
            secteur="ESN",
            localisation=localisation,
            site_web=site_web,
            notes=f"Source : La Bonne Alternance | NAF : {naf_label}" if naf_label else "Source : La Bonne Alternance",
        )
        db.session.add(entreprise)
        db.session.flush()  # pour obtenir l'id avant commit

    # Créer la candidature spontanée
    date_envoi = datetime.utcnow().date()
    candidature = Candidature(
        entreprise_id=entreprise.id,
        poste="Candidature spontanée — MOA / PO / Dev",
        type_contrat="Stage",
        date_envoi=date_envoi,
        statut="À envoyer",
        lien_offre=lien_offre,
        date_relance=date_envoi + timedelta(days=7),
        notes="Ajoutée depuis La Bonne Alternance — candidature spontanée",
    )
    db.session.add(candidature)
    db.session.commit()

    flash(f'"{nom}" ajouté au pipeline.', "success")
    return redirect(url_for("offres.index"))