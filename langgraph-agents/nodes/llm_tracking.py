import logging
from datetime import date, datetime

from db import log_llm_call

logger = logging.getLogger(__name__)

# (date de fin du tarif d'intro incluse, $/1M tokens input, $/1M tokens output)
# None = tarif courant, sans date de fin. Le tarif d'intro sonnet-5 expire le 2026-08-31.
_PRICING = {
    "claude-sonnet-5": [
        (date(2026, 8, 31), 2.00, 10.00),
        (None, 3.00, 15.00),
    ],
    "claude-haiku-4-5": [
        (None, 1.00, 5.00),
    ],
}


def _prix_par_million(model: str) -> tuple[float, float]:
    today = datetime.now().date()
    for until, prix_in, prix_out in _PRICING.get(model, []):
        if until is None or today <= until:
            return prix_in, prix_out
    return 0.0, 0.0


def track_llm_call(candidature_id: int, node: str, model: str, ai_message) -> None:
    """Logge coût/tokens d'un appel LLM à partir des usage_metadata d'un AIMessage."""
    usage = getattr(ai_message, "usage_metadata", None) or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    if not input_tokens and not output_tokens:
        logger.warning("track_llm_call: pas d'usage_metadata (node=%s, model=%s)", node, model)
        return

    prix_in, prix_out = _prix_par_million(model)
    cost_usd = (input_tokens * prix_in + output_tokens * prix_out) / 1_000_000

    log_llm_call(candidature_id, node, model, input_tokens, output_tokens, cost_usd)
