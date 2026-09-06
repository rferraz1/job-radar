# tests/test_enrich_provider_gemini.py
import json
import pytest
from enrich.providers.base import LLMRespostaInvalida, LLMIndisponivel
from enrich.providers.gemini import GeminiProvider

BOM = json.dumps({"compat_score": 80, "compat_reasoning": "ok", "verdict": "avaliar"})


class _FakeClient:
    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.chamadas = 0
        self.models = self

    def generate_content(self, **kwargs):
        self.chamadas += 1
        r = self._respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return type("Resp", (), {"text": r})()


def test_json_valido_de_primeira():
    p = GeminiProvider(cliente=_FakeClient([BOM]))
    d = p.analisar("prompt")
    assert d["compat_score"] == 80
    assert p._cliente.chamadas == 1


def test_json_sujo_faz_retry_e_recupera():
    p = GeminiProvider(cliente=_FakeClient(["não é json", "```json\n" + BOM + "\n```"]))
    d = p.analisar("prompt")
    assert d["compat_score"] == 80
    assert p._cliente.chamadas == 2


def test_json_ruim_nas_duas_levanta_invalida():
    p = GeminiProvider(cliente=_FakeClient(["lixo", "mais lixo"]))
    with pytest.raises(LLMRespostaInvalida):
        p.analisar("prompt")


def test_erro_de_rede_levanta_indisponivel():
    p = GeminiProvider(cliente=_FakeClient([ConnectionError("timeout")]))
    with pytest.raises(LLMIndisponivel):
        p.analisar("prompt")
