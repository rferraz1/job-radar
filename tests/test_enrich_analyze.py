# tests/test_enrich_analyze.py
import pytest
from enrich.analyze import analisar_vaga, analisar_vagas
from enrich.providers.base import LLMIndisponivel, LLMRespostaInvalida
from job import Job

BOM = {"compat_score": 90, "compat_reasoning": "forte", "verdict": "candidatar",
       "salary_estimate": {"min": 4000, "max": 6000}}


def _job(t="DevOps Júnior"):
    return Job(titulo=t, empresa="ACME", local="Remoto", link="http://x/1", site="S", descricao="Terraform, AWS.")


class _Prov:
    def __init__(self, resultado):
        self.resultado = resultado
        self.chamadas = 0

    def analisar(self, prompt):
        self.chamadas += 1
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self.resultado


def test_sucesso_devolve_analysis():
    a = analisar_vaga(_job(), "CV texto", _Prov(BOM))
    assert a.compat_score == 90
    assert a.verdict == "candidatar"


def test_provider_resposta_invalida_devolve_none():
    assert analisar_vaga(_job(), "CV", _Prov(LLMRespostaInvalida("sem json"))) is None


def test_provider_indisponivel_propaga():
    # LLMIndisponivel NÃO é capturado por analisar_vaga — sobe pro orquestrador.
    with pytest.raises(LLMIndisponivel):
        analisar_vaga(_job(), "CV", _Prov(LLMIndisponivel("rate limit")))


def test_json_incompleto_devolve_none():
    assert analisar_vaga(_job(), "CV", _Prov({"compat_score": 50})) is None  # sem verdict


def test_analisar_vagas_para_apos_n_falhas(monkeypatch):
    import enrich.analyze as az
    prov = _Prov(LLMIndisponivel("quota"))
    monkeypatch.setattr(az, "obter_provider", lambda: prov)
    monkeypatch.setattr(az, "carregar_cv", lambda: "CV")
    monkeypatch.setattr("config.ENRICH_MAX_FALHAS_LLM", 2, raising=False)
    jobs = [_job(f"vaga {i}") for i in range(5)]
    analisar_vagas(jobs)
    assert prov.chamadas == 2  # parou após 2 falhas
    assert all(j.analise is None for j in jobs)


def test_analisar_vagas_seta_in_place(monkeypatch):
    import enrich.analyze as az
    monkeypatch.setattr(az, "obter_provider", lambda: _Prov(BOM))
    monkeypatch.setattr(az, "carregar_cv", lambda: "CV")
    jobs = [_job()]
    analisar_vagas(jobs)
    assert jobs[0].analise.compat_score == 90
