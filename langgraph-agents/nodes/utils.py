def extract_text(response) -> str:
    """Extrait le texte d'une réponse LangChain (string ou liste de blocs).

    Lève une exception si aucun bloc 'text' n'est présent (ex: réponse
    tronquée pendant la réflexion, avant la sortie finale) plutôt que de
    retourner le repr brut des blocs (thinking/signature) comme texte.
    """
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block["text"]
            if hasattr(block, "type") and block.type == "text":
                return block.text
    stop_reason = getattr(response, "response_metadata", {}).get("stop_reason")
    raise ValueError(
        f"Aucun bloc 'text' dans la réponse Claude (stop_reason={stop_reason}) : {content!r}"
    )
