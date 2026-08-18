import re

PHRASES_INTERDITES = [
    "C'est avec grand intérêt",
    "c'est avec grand intérêt",
    "peu de profils",
]

CLOSING_OBLIGATOIRE = "Je suis disponible pour un échange"


def check_programmatique(lm: str, type_contrat: str = "non précisé") -> list[str]:
    """Checks déterministes de conformité d'une lettre de motivation.

    Module indépendant de LangGraph/langchain — testable sans dépendances externes.
    """
    motifs = []

    if "—" in lm:
        motifs.append("Tiret em (—) présent — utiliser '-' ou reformuler")

    for phrase in PHRASES_INTERDITES:
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

    if CLOSING_OBLIGATOIRE not in lm:
        motifs.append("Closing manquant ou incorrect — doit terminer par 'Je suis disponible pour un échange.'")

    return motifs
