from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from nodes.llm_tracking import track_llm_call
from state import LMState

_MODEL = "claude-sonnet-5"
_llm_base = ChatAnthropic(model=_MODEL, max_tokens=4096, thinking={"type": "disabled"})


class LMOutput(BaseModel):
    lm: str = Field(description="Corps de la lettre de motivation (250 à 320 mots)")
    message_email: str = Field(description="Corps du message d'accompagnement (60 à 100 mots)")


_llm = _llm_base.with_structured_output(LMOutput, include_raw=True)

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
- INTERDIT : tiret em (—), "C'est avec grand intérêt", "peu de profils"
- CesedaIA = toujours "en cours", jamais "en production"
- MSc Epitech = toujours "octobre 2026"
- Gap technique détecté dans l'offre : le nommer, montrer le domaine adjacent maîtrisé, affirmer la montée en compétence rapide
- Termine OBLIGATOIREMENT par : "Je suis disponible pour un échange."

CONSIGNES SELON LE TYPE DE CONTRAT (champ analyse.type_contrat) :
- "alternance" ou "non précisé" : ne rien changer de fondamental. Mettre en avant en priorité les projets personnels (Job Tracker, Fretexia, Saveurs Méditerranéennes, CesedaIA) et présenter les stages comme des stages.
- "CDI" ou "freelance" ou "CDI et freelance" : garder le mot "stage" pour MOSLTRANS et Saveurs Méditerranéennes (ne jamais mentir sur le statut, le CV les affiche comme stages), mais leur donner plus de poids : décrire les livrables concrets et l'autonomie réelle (architecture définie seul, MVP en prod, RAG en prod, périmètre business), comme une expérience professionnelle à part entière plutôt que comme un stagiaire en observation. Ne jamais se positionner comme senior — rester factuel sur le niveau réel (reconversion + 6 ans Siemens + stages), sans survendre.
- Mention de la micro-entreprise/freelance : UNIQUEMENT si analyse.type_contrat vaut "freelance" ou "CDI et freelance" (l'offre propose explicitement un TJM en alternative au salarié). Dans ce cas, mentionner le statut de micro-entrepreneur comme option recevable pour la mission. Si type_contrat est "alternance", "CDI" ou "non précisé" : ne jamais l'évoquer.

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
    type_contrat = analyse.get("type_contrat", "non précisé")

    prompt = f"""Rédige la lettre de motivation et le message d'accompagnement pour ce poste.

Type de contrat détecté : {type_contrat}

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

    result = _llm.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ])
    if result["parsing_error"] is not None:
        raise result["parsing_error"]
    parsed: LMOutput = result["parsed"]
    track_llm_call(state["candidature_id"], "redacteur", _MODEL, result["raw"])

    return {
        "lm_courante": parsed.lm.strip(),
        "message_email": parsed.message_email.strip(),
        "nb_iterations": state.get("nb_iterations", 0) + 1,
        "motifs_rejet": [],
    }
