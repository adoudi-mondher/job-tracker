from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from state import EntretienState

_llm_base = ChatAnthropic(model="claude-sonnet-5", max_tokens=4096, thinking={"type": "disabled"})


class InterviewPrepOutput(BaseModel):
    pitch: str = Field(description="Pitch de présentation pour l'entretien (30-45 secondes à l'oral, 80-120 mots)")
    hard_skills: str = Field(description="Compétences techniques à mettre en avant, en lien avec la stack demandée, sous forme de liste à puces (- ...)")
    soft_skills: str = Field(description="Soft skills pertinents pour ce poste/secteur, sous forme de liste à puces (- ...), chacun justifié par un exemple concret du profil")
    transposition_stack: str = Field(description="Si la stack de l'offre diverge de la stack maîtrisée : explication de la transposition (domaine adjacent maîtrisé → montée en compétence). Si la stack correspond déjà, dire explicitement qu'il n'y a pas d'écart notable.")


_llm = _llm_base.with_structured_output(InterviewPrepOutput)

_REGLES = (Path(__file__).parent.parent / "regles_redaction.md").read_text(encoding="utf-8")

_SYSTEM = f"""Tu es un coach spécialisé en préparation d'entretiens techniques et RH.

Voici le profil complet du candidat :

{_REGLES}

---

CONSIGNES GÉNÉRALES :
- Tu prépares le candidat à passer l'entretien pour CE poste précis, pas une fiche générique.
- Style direct, factuel, sobre — pas de superlatifs, pas d'emphase. Jamais de survente ("expert", "senior") si le profil ne le justifie pas.
- Base-toi sur l'analyse de l'offre (stack demandée, secteur, niveau) et sur le profil candidat ci-dessus.
- Un champ "contexte libre" (notes prises par le candidat) peut être fourni : il peut contenir des informations datées ou sans rapport avec l'entretien (relances, suivi administratif...). N'utilise que ce qui est pertinent pour préparer CET entretien (type d'entretien, interlocuteurs, sujets annoncés, points sur lesquels le candidat veut être rassuré) et ignore le reste sans le mentionner.
- Gap technique entre stack maîtrisée et stack demandée : ne jamais le nier, toujours le nommer et montrer le domaine adjacent maîtrisé + la capacité de montée en compétence rapide (même logique que pour la lettre de motivation).
- CesedaIA = toujours "en cours", jamais "en production". MSc Epitech = toujours "octobre 2026".
"""


def coach_node(state: EntretienState) -> dict:
    analyse = state.get("analyse", {})
    type_contrat = analyse.get("type_contrat", "non précisé")

    prompt = f"""Prépare le pitch et les points clés pour cet entretien.

Type de contrat détecté : {type_contrat}

Analyse structurée de l'offre :
{analyse}

Contexte complémentaire :
- Poste : {state['poste']}
- Entreprise : {state['entreprise_nom']}
- Secteur : {state['secteur']}
- Résumé de l'offre : {state['resume_offre']}
- Stack technique demandée : {state['stack_technique']}

Contexte libre (notes du candidat, à filtrer — ne garder que ce qui concerne cet entretien) :
{state.get('notes', '') or '(aucun)'}
"""

    parsed: InterviewPrepOutput = _llm.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ])

    prep = f"""🎯 PITCH

{parsed.pitch.strip()}

💪 HARD SKILLS

{parsed.hard_skills.strip()}

🤝 SOFT SKILLS

{parsed.soft_skills.strip()}

🔄 TRANSPOSITION STACK

{parsed.transposition_stack.strip()}"""

    return {"prep_entretien": prep}
