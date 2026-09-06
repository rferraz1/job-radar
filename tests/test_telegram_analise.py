from notifier.telegram import _bloco_analise, montar_digest
from enrich.models import Analysis


def _an(**kw):
    base = {"compat_score": 88, "compat_reasoning": "Stack bate.", "verdict": "candidatar",
            "verdict_reason": "sem bloqueio",
            "salary_estimate": {"min": 3500, "max": 5000, "confianca": "media"},
            "gaps": [{"requisito": "Kubernetes", "severidade": "importante"},
                     {"requisito": "Inglês fluente", "severidade": "bloqueante"}]}
    base.update(kw)
    return Analysis.from_dict(base)


def test_bloco_analise_tem_score_salario_e_gaps():
    txt = _bloco_analise(_an())
    assert "88%" in txt
    assert "3500" in txt and "5000" in txt
    assert "Kubernetes" in txt
    assert "Inglês fluente" in txt  # bloqueante aparece
    assert "candidatar" in txt.lower()


def test_bloco_analise_none_vira_vazio():
    assert _bloco_analise(None) == ""


def test_digest_mostra_compat_quando_tem(monkeypatch):
    # tupla: (titulo, empresa, link, relevancia, exploratoria, compat_score, analise_json)
    linhas = [("DevOps Jr", "ACME", "http://x/1", 5, 0, 91, _an(compat_score=91).to_json())]
    msgs = montar_digest(linhas, "Brasil")
    assert any("91%" in m for m in msgs)
