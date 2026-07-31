import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Charge le .env du projet parent (job-tracker/.env)
load_dotenv(Path(__file__).parent.parent / ".env")

import requests
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

from db import ensure_table, log_run
from graph import entretien_graph, lm_graph
from state import EntretienState, LMState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_table()
    yield


app = FastAPI(title="LangGraph LM Service", lifespan=lifespan)


class GenerateLMRequest(BaseModel):
    candidature_id: int
    poste: str
    entreprise_nom: str
    secteur: str = ""
    resume_offre: str = ""
    stack_technique: str = ""


class GenerateInterviewPrepRequest(BaseModel):
    candidature_id: int
    poste: str
    entreprise_nom: str
    secteur: str = ""
    resume_offre: str = ""
    stack_technique: str = ""
    notes: str = ""


def _run_graph(req: GenerateLMRequest) -> None:
    initial_state: LMState = {
        "candidature_id": req.candidature_id,
        "poste": req.poste,
        "entreprise_nom": req.entreprise_nom,
        "secteur": req.secteur,
        "resume_offre": req.resume_offre,
        "stack_technique": req.stack_technique,
        "analyse": {},
        "lm_courante": "",
        "message_email": "",
        "motifs_rejet": [],
        "nb_iterations": 0,
        "verification": {"conforme": False, "motifs": []},
    }

    try:
        final_state = lm_graph.invoke(initial_state)
    except Exception as exc:
        logger.error("Graph error candidature %s: %s", req.candidature_id, exc)
        return

    lm = final_state["lm_courante"]
    message_email = final_state.get("message_email", "")
    verification = final_state["verification"]
    nb_iter = final_state["nb_iterations"]

    if verification["conforme"]:
        statut = "conforme"
    elif nb_iter >= 2:
        statut = "max_iterations"
    else:
        statut = "non_conforme"

    logger.info(
        "=== LM GÉNÉRÉE (candidature %s | statut=%s | %d itération(s)) ===\n%s\n=== FIN LM ===",
        req.candidature_id, statut, nb_iter, lm,
    )

    flask_url = os.environ.get("FLASK_API_URL", "http://job-tracker:5000")
    token = os.environ.get("APP_PASSWORD", "changeme")
    try:
        payload = {"lettre_motivation": lm}
        if message_email:
            payload["message_accompagnement"] = message_email
        resp = requests.patch(
            f"{flask_url}/api/candidatures/{req.candidature_id}",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Write-back OK candidature %s statut=%s", req.candidature_id, statut)
    except Exception as exc:
        logger.error("Write-back failed candidature %s: %s", req.candidature_id, exc)

    try:
        log_run(
            candidature_id=req.candidature_id,
            analyse=final_state.get("analyse", {}),
            lm_finale=lm,
            statut=statut,
            motifs=verification.get("motifs", []),
            nb_iterations=nb_iter,
        )
    except Exception as exc:
        logger.error("DB log failed candidature %s: %s", req.candidature_id, exc)


@app.post("/generate-lm", status_code=202)
async def generate_lm(req: GenerateLMRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_graph, req)
    return {"status": "accepted", "candidature_id": req.candidature_id}


def _run_graph_entretien(req: GenerateInterviewPrepRequest) -> None:
    initial_state: EntretienState = {
        "candidature_id": req.candidature_id,
        "poste": req.poste,
        "entreprise_nom": req.entreprise_nom,
        "secteur": req.secteur,
        "resume_offre": req.resume_offre,
        "stack_technique": req.stack_technique,
        "notes": req.notes,
        "analyse": {},
        "prep_entretien": "",
    }

    try:
        final_state = entretien_graph.invoke(initial_state)
    except Exception as exc:
        logger.error("Graph entretien error candidature %s: %s", req.candidature_id, exc)
        return

    prep_entretien = final_state["prep_entretien"]

    logger.info(
        "=== PRÉPARATION ENTRETIEN GÉNÉRÉE (candidature %s) ===\n%s\n=== FIN ===",
        req.candidature_id, prep_entretien,
    )

    flask_url = os.environ.get("FLASK_API_URL", "http://job-tracker:5000")
    token = os.environ.get("APP_PASSWORD", "changeme")
    try:
        resp = requests.patch(
            f"{flask_url}/api/candidatures/{req.candidature_id}",
            json={"prep_entretien": prep_entretien},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Write-back OK candidature %s (prep_entretien)", req.candidature_id)
    except Exception as exc:
        logger.error("Write-back failed candidature %s: %s", req.candidature_id, exc)


@app.post("/generate-interview-prep", status_code=202)
async def generate_interview_prep(req: GenerateInterviewPrepRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_graph_entretien, req)
    return {"status": "accepted", "candidature_id": req.candidature_id}
