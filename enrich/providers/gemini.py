import json
import re

from logger import get_logger
from .base import LLMProvider, LLMIndisponivel, LLMRespostaInvalida

logger = get_logger()

_MODELO = "gemini-2.5-flash"


def _extrair_json(texto: str) -> dict:
    texto = texto.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.DOTALL)
    candidato = m.group(1) if m else texto
    inicio, fim = candidato.find("{"), candidato.rfind("}")
    if inicio == -1 or fim == -1:
        raise ValueError("sem objeto JSON no texto")
    return json.loads(candidato[inicio:fim + 1])


class GeminiProvider(LLMProvider):
    def __init__(self, cliente=None, api_key: str | None = None):
        if cliente is not None:
            self._cliente = cliente
            return
        from config import GEMINI_API_KEY
        from google import genai  # import tardio: só quem usa Gemini precisa da lib
        chave = api_key or GEMINI_API_KEY
        if not chave:
            raise LLMIndisponivel("GEMINI_API_KEY não configurada")
        self._cliente = genai.Client(api_key=chave)

    def analisar(self, prompt: str) -> dict:
        ultimo_texto = ""
        for tentativa in (1, 2):
            try:
                resp = self._cliente.models.generate_content(
                    model=_MODELO,
                    contents=prompt if tentativa == 1 else prompt + "\n\nATENÇÃO: responda SÓ o JSON, nada mais.",
                    config={"response_mime_type": "application/json", "temperature": 0.2},
                )
            except Exception as e:  # rede, auth, rate-limit, quota
                raise LLMIndisponivel(f"Gemini: {type(e).__name__}: {e}") from e
            ultimo_texto = getattr(resp, "text", "") or ""
            try:
                return _extrair_json(ultimo_texto)
            except (ValueError, json.JSONDecodeError):
                logger.warning(f"[gemini] resposta não-JSON (tentativa {tentativa}): {ultimo_texto[:120]!r}")
        raise LLMRespostaInvalida(f"Gemini não devolveu JSON válido em 2 tentativas: {ultimo_texto[:200]!r}")
