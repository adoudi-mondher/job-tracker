import json

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from nodes.utils import extract_text
from state import LMState

_llm = ChatAnthropic(model="claude-haiku-4-5", max_tokens=1024)

_SYSTEM = """Tu es un analyste de recrutement. Analyse l'offre d'emploi et extrais les informations clés.
Retourne UNIQUEMENT un objet JSON valide avec les champs suivants :
- poste (string)
- secteur (string)
- stack_demandee (liste de strings)
- niveau_requis (string : "Bac+3" | "Bac+4" | "Bac+5" | "non précisé")
- mots_cles (liste de strings, 3 à 5 éléments différenciants)
"""


def analyste_node(state: LMState) -> dict:
    contenu = f"""Poste : {state['poste']}
Entreprise : {state['entreprise_nom']}
Secteur déclaré : {state['secteur']}
Résumé de l'offre : {state['resume_offre']}
Stack technique mentionnée : {state['stack_technique']}"""

    response = _llm.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=contenu),
    ])

    raw = extract_text(response).strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        analyse = json.loads(raw)
    except json.JSONDecodeError:
        analyse = {
            "poste": state["poste"],
            "secteur": state["secteur"],
            "stack_demandee": [],
            "niveau_requis": "non précisé",
            "mots_cles": [],
        }

    return {"analyse": analyse}
