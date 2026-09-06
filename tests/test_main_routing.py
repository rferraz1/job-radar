import main
from job import Job
from enrich.models import Analysis


def _job(rel=0):
    j = Job(titulo="X", empresa="Y", local="Remoto", link="http://x/1", site="S")
    j.relevancia = rel
    return j


def _an(score):
    return Analysis.from_dict({"compat_score": score, "compat_reasoning": "x", "verdict": "avaliar"})


def test_analise_acima_do_limiar_notifica():
    j = _job(); j.analise = _an(90)
    assert main._deve_notificar_imediato(j) is True


def test_analise_abaixo_vai_pro_digest():
    j = _job(rel=9); j.analise = _an(50)  # relevancia alta não salva: com análise, manda a análise
    assert main._deve_notificar_imediato(j) is False


def test_sem_analise_usa_relevancia():
    assert main._deve_notificar_imediato(_job(rel=8)) is True
    assert main._deve_notificar_imediato(_job(rel=4)) is False


def test_vaga_antiga_nunca_imediata(monkeypatch):
    j = _job(); j.analise = _an(99)
    monkeypatch.setattr(type(j), "publicacao_antiga", property(lambda self: True))
    assert main._deve_notificar_imediato(j) is False
