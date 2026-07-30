import json
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from nodes.utils import extract_text
from state import LMState

_llm = ChatAnthropic(model="claude-haiku-4-5", max_tokens=512)

_PHRASES_INTERDITES = [
    "C'est avec grand intérêt",
    "c'est avec grand intérêt",
    "peu de profils",
]


def _check_programmatique(lm: str, type_contrat: str = "non précisé") -> list[str]:
    motifs = []

    if "—" in lm:
        motifs.append("Tiret em (—) présent — utiliser '-' ou reformuler")

    for phrase in _PHRASES_INTERDITES:
        if phrase in lm:
            motifs.append(f"Phrase interdite : '{phrase}'")

    if "micro-entreprise" in lm.lower() and type_contrat not in ("freelance", "CDI et freelance"):
        motifs.append(
            "Mention de la micro-entreprise alors que l'offre ne propose pas explicitement de freelance "
            f"(type_contrat détecté : '{type_contrat}') — à retirer"
        )

    if re.search(r"CesedaIA.{0,30}en production", lm, re.IGNORECASE):
        motifs.append("CesedaIA présenté comme 'en production' — doit être 'en cours'")

    if ("MSc" in lm or "Epitech" in lm) and "octobre 2026" not in lm:
        motifs.append("MSc Epitech mentionné sans préciser 'octobre 2026'")

    word_count = len(lm.split())
    if word_count < 250:
        motifs.append(f"Trop court : {word_count} mots (minimum 250)")
    elif word_count > 320:
        motifs.append(f"Trop long : {word_count} mots (maximum 320)")

    if "Je suis disponible pour un échange" not in lm:
        motifs.append("Closing manquant ou incorrect — doit terminer par 'Je suis disponible pour un échange.'")

    return motifs


def verificateur_node(state: LMState) -> dict:
    lm = state["lm_courante"]
    type_contrat = state.get("analyse", {}).get("type_contrat", "non précisé")
    motifs = _check_programmatique(lm, type_contrat)

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
