"""Alerta de falha via WhatsApp — mesmo padrão do `agentes/core/alertas.py`
(propositalmente duplicado, não importado: repositórios/venvs separados).
Reusa o `/notify` do `workout-generator/whatsapp-bot`. Nunca levanta.
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

_NOTIFY_URL = os.getenv("ALERTA_NOTIFY_URL", "http://127.0.0.1:3000/notify")


def avisar_falha(detalhe: str) -> None:
    try:
        resp = requests.post(_NOTIFY_URL, json={"text": f"⚠️ [jobradar] {detalhe}"}, timeout=5)
        if resp.status_code >= 400:
            logger.warning("[alertas] notify respondeu %s: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.warning("[alertas] falha ao notificar (%s): %s", type(e).__name__, e)
