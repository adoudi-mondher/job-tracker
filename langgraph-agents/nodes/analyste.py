import json

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from nodes.llm_tracking import track_llm_call
from nodes.utils import extract_text
from state import LMState

_MODEL = "claude-haiku-4-5"
_llm = ChatAnthropic(model=_MODEL, max_tokens=1024)

_SYSTEM = """Tu es un analyste de recrutement. Analyse l'offre d'emploi et extrais les informations clés.
Retourne UNIQUEMENT un objet JSON valide avec les champs suivants :
- poste (string)
- secteur (string)
- stack_demandee (liste de strings)
- niveau_requis (string : "Bac+3" | "Bac+4" | "Bac+5" | "non précisé")
- mots_cles (liste de strings, 3 à 5 éléments différenciants)
- type_contrat (string : "alternance" | "CDI" | "freelance" | "CDI et freelance" | "non précisé")

Pour type_contrat, explore minutieusement le texte de l'offre à la recherche de signaux explicites :
- "alternance", "apprentissage", "contrat de professionnalisation", "alternant(e)" → "alternance"
- "CDI", un salaire brut annuel seul, "statut cadre" → "CDI"
- "freelance", "indépendant", "TJM", "€/jour", "€/j", "portage salarial" seul → "freelance"
- Si l'offre mentionne à la fois un salaire ET un tarif journalier freelance (ex. "Salaire : 50-60 K€" et "Freelance : 350-460€/J") → "CDI et freelance"
- Si aucun signal net → "non précisé"
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
    track_llm_call(state["candidature_id"], "analyste", _MODEL, response)

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
            "type_contrat": "non précisé",
        }

    return {"analyse": analyse}
