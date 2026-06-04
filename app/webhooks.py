"""
Utilitaire webhooks sortants — fire & forget
Envoie les webhooks n8n dans un thread daemon pour ne pas bloquer la requete.
Les erreurs sont loggees mais jamais remontees a l'utilisateur.
"""
import logging
import threading

import requests

logger = logging.getLogger(__name__)


def _fire(url: str, payload: dict, timeout: int = 5) -> None:
    """Envoie le webhook dans un thread secondaire (daemon)."""
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        logger.info("Webhook envoye vers %s — status %s", url, resp.status_code)
    except Exception as exc:
        # Ne jamais propager — l'utilisateur ne doit pas voir d'erreur
        logger.warning("Webhook echec vers %s : %s", url, exc)


def send_webhook(url: str, payload: dict) -> None:
    """
    Lance le webhook en arriere-plan si l'URL est configuree.
    Usage :
        send_webhook(current_app.config['N8N_WEBHOOK_ENRICH'],
                     {'candidature_id': c.id, 'url': c.lien_offre})
    """
    if not url:
        return  # Webhook non configure — on ignore silencieusement
    t = threading.Thread(target=_fire, args=(url, payload), daemon=True)
    t.start()
