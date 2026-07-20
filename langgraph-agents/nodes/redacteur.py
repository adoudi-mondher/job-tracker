from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from nodes.utils import extract_text
from state import LMState

_llm = ChatAnthropic(model="claude-sonnet-5", max_tokens=2048)

_REGLES = (Path(__file__).parent.parent / "regles_redaction.md").read_text(encoding="utf-8")

_SYSTEM = f"""Tu es un rédacteur expert en lettres de motivation professionnelles.

Voici le profil complet du candidat et les règles de rédaction à respecter :

{_REGLES}

---

CONSIGNES STRICTES :
- Rédige UNIQUEMENT le corps de la lettre (sans en-tête, sans "Cordialement,", sans signature)
- 250 à 320 mots exactement - compte les mots
- Commence par l'entreprise ou le secteur, jamais par soi-même
- Style direct, factuel, sobre - pas de superlatifs, pas d'emphase
- INTERDIT : tiret em (—), "C'est avec grand intérêt", "peu de profils", mention micro-entreprise
- CesedaIA = toujours "en cours", jamais "en production"
- MSc Epitech = toujours "octobre 2026"
- Gap technique détecté dans l'offre : le nommer, montrer le domaine adjacent maîtrisé, affirmer la montée en compétence rapide
- Termine OBLIGATOIREMENT par : "Je suis disponible pour un échange."
"""


def redacteur_node(state: LMState) -> dict:
    analyse = state.get("analyse", {})
    motifs = state.get("motifs_rejet", [])

    prompt = f"""Rédige la lettre de motivation pour ce poste.

Analyse structurée de l'offre :
{analyse}

Contexte complémentaire :
- Entreprise : {state['entreprise_nom']}
- Secteur : {state['secteur']}
- Résumé de l'offre : {state['resume_offre']}
- Stack technique demandée : {state['stack_technique']}
"""

    if motifs:
        prompt += f"\n\nCORRECTION DEMANDÉE (itération {state.get('nb_iterations', 1) + 1}) — corrige impérativement ces points :\n"
        for m in motifs:
            prompt += f"- {m}\n"
        prompt += "\nRéécris la lettre en corrigeant TOUS ces points."

    response = _llm.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ])

    return {
        "lm_courante": extract_text(response).strip(),
        "nb_iterations": state.get("nb_iterations", 0) + 1,
        "motifs_rejet": [],
    }
