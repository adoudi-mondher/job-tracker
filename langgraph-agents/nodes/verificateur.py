import json

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from nodes.llm_tracking import track_llm_call
from nodes.utils import extract_text
from state import LMState
from verification import check_programmatique

_MODEL = "claude-haiku-4-5"
_llm = ChatAnthropic(model=_MODEL, max_tokens=512)


def verificateur_node(state: LMState) -> dict:
    lm = state["lm_courante"]
    type_contrat = state.get("analyse", {}).get("type_contrat", "non précisé")
    motifs = check_programmatique(lm, type_contrat)

    # Vérification LLM du ton uniquement si les checks programmatiques passent
    if not motifs:
        response = _llm.invoke([
            SystemMessage(content="""Tu vérifies le TON d'une lettre de motivation professionnelle.
Réponds UNIQUEMENT en JSON valide : {"ok": true} ou {"ok": false, "motifs": ["motif précis 1"]}

Rejette UNIQUEMENT si tu trouves un de ces problèmes concrets :
- Superlatif ou emphase excessive ("passionné", "profondément motivé", "je suis le candidat idéal")
- Comparatif implicite valorisant ("peu de profils ont", "profil rare")
- Formule générique creuse sans contenu factuel ("je suis très motivé par votre entreprise")
- Gap technique ignoré alors que l'offre mentionne une stack absente du profil

Si la lettre est directe, factuelle et sobre — même imparfaite stylistiquement — réponds {"ok": true}.
En cas de doute, réponds {"ok": true}."""),
            HumanMessage(content=f"Lettre à vérifier :\n\n{lm}"),
        ])
        track_llm_call(state["candidature_id"], "verificateur", _MODEL, response)

        raw = extract_text(response).strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            result = json.loads(raw)
            if not result.get("ok", True):
                motifs.extend(result.get("motifs", []))
        except json.JSONDecodeError:
            pass  # check LLM échoue → ne bloque pas

    conforme = len(motifs) == 0
    return {
        "verification": {"conforme": conforme, "motifs": motifs},
        "motifs_rejet": motifs,
    }
