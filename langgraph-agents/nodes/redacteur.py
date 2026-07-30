from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from state import LMState

_llm_base = ChatAnthropic(model="claude-sonnet-5", max_tokens=4096, thinking={"type": "disabled"})


class LMOutput(BaseModel):
    lm: str = Field(description="Corps de la lettre de motivation (250 à 320 mots)")
    message_email: str = Field(description="Corps du message d'accompagnement (60 à 100 mots)")


_llm = _llm_base.with_structured_output(LMOutput)

_REGLES = (Path(__file__).parent.parent / "regles_redaction.md").read_text(encoding="utf-8")

_SYSTEM = f"""Tu es un rédacteur expert en lettres de motivation professionnelles.

Voici le profil complet du candidat et les règles de rédaction à respecter :

{_REGLES}

---

CONSIGNES LETTRE DE MOTIVATION :
- Rédige UNIQUEMENT le corps de la lettre (sans en-tête, sans "Cordialement,", sans signature)
- 250 à 320 mots exactement - compte les mots
- Commence par l'entreprise ou le secteur, jamais par soi-même
- Style direct, factuel, sobre - pas de superlatifs, pas d'emphase
- INTERDIT : tiret em (—), "C'est avec grand intérêt", "peu de profils", mention micro-entreprise
- CesedaIA = toujours "en cours", jamais "en production"
- MSc Epitech = toujours "octobre 2026"
- Gap technique détecté dans l'offre : le nommer, montrer le domaine adjacent maîtrisé, affirmer la montée en compétence rapide
- Termine OBLIGATOIREMENT par : "Je suis disponible pour un échange."

CONSIGNES MESSAGE D'ACCOMPAGNEMENT (corps du mail) :
- 3 à 5 phrases, 60 à 100 mots
- Commence par une accroche directe sur le poste ou l'entreprise (pas "Madame, Monsieur")
- 1 phrase reliant le profil au poste de manière concrète
- Mentionne que CV et lettre de motivation sont en pièce jointe
- Termine par une courte disponibilité (ex. "Disponible pour un échange à votre convenance.")
- Ton naturel et direct — ni trop formel, ni familier
"""


def redacteur_node(state: LMState) -> dict:
    analyse = state.get("analyse", {})
    motifs = state.get("motifs_rejet", [])

    prompt = f"""Rédige la lettre de motivation et le message d'accompagnement pour ce poste.

Analyse structurée de l'offre :
{analyse}

Contexte complémentaire :
- Entreprise : {state['entreprise_nom']}
- Secteur : {state['secteur']}
- Résumé de l'offre : {state['resume_offre']}
- Stack technique demandée : {state['stack_technique']}
"""

    if motifs:
        prompt += f"\n\nCORRECTION DEMANDÉE (itération {state.get('nb_iterations', 1) + 1}) — corrige impérativement ces points dans la LM :\n"
        for m in motifs:
            prompt += f"- {m}\n"
        prompt += "\nRéécris la LM en corrigeant TOUS ces points. Le message_email peut rester identique si non concerné."

    parsed: LMOutput = _llm.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ])

    return {
        "lm_courante": parsed.lm.strip(),
        "message_email": parsed.message_email.strip(),
        "nb_iterations": state.get("nb_iterations", 0) + 1,
        "motifs_rejet": [],
    }
