# tests/test_enrich_models.py
import pytest
from enrich.models import Analysis

VALIDO = {
    "compat_score": 88,
    "compat_reasoning": "Stack Node/React bate; transição de carreira coerente.",
    "salary_estimate": {"min": 3000, "max": 4500, "moeda": "BRL", "periodo": "mes",
                        "confianca": "media", "base": "faixa típica de júnior remoto"},
    "gaps": [{"requisito": "Kubernetes", "severidade": "importante", "tenho_parcial": False}],
    "strengths": ["Projetos reais de RAG/agentes"],
    "verdict": "candidatar",
    "verdict_reason": "Bom fit, sem gap bloqueante.",
}


def test_from_dict_valido():
    a = Analysis.from_dict(VALIDO)
    assert a.compat_score == 88
    assert a.salary_estimate.min == 3000
    assert a.gaps[0].severidade == "importante"
    assert a.verdict == "candidatar"


def test_score_fora_de_range_e_clampado():
    a = Analysis.from_dict({**VALIDO, "compat_score": 140})
    assert a.compat_score == 100
    a2 = Analysis.from_dict({**VALIDO, "compat_score": -5})
    assert a2.compat_score == 0


def test_campos_faltando_levanta():
    with pytest.raises(ValueError):
        Analysis.from_dict({"compat_score": 50})  # sem verdict etc.


def test_verdict_invalido_vira_avaliar():
    a = Analysis.from_dict({**VALIDO, "verdict": "talvez"})
    assert a.verdict == "avaliar"


def test_roundtrip_json():
    a = Analysis.from_dict(VALIDO)
    b = Analysis.from_dict(__import__("json").loads(a.to_json()))
    assert b.compat_score == a.compat_score
