def extract_text(response) -> str:
    """Extrait le texte d'une réponse LangChain (string ou liste de blocs)."""
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block["text"]
            if hasattr(block, "type") and block.type == "text":
                return block.text
    return str(content)
