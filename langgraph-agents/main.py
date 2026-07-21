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
from graph import lm_graph
from state import LMState

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
        resp = requests.patch(
            f"{flask_url}/api/candidatures/{req.candidature_id}",
            json={"lettre_motivation": lm},
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
