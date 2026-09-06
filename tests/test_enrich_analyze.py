# tests/test_enrich_analyze.py
import pytest

import database.database as db
from enrich.analyze import analisar_vaga, analisar_vagas
from enrich.providers.base import LLMIndisponivel, LLMRespostaInvalida
from job import Job

BOM = {"compat_score": 90, "compat_reasoning": "forte", "verdict": "candidatar",
       "salary_estimate": {"min": 4000, "max": 6000}}


@pytest.fixture(autouse=True)
def _db_isolado(tmp_path, monkeypatch):
    """Todo teste que chama analisar_vagas toca metadados (latch diário de
    LLM) — isola num banco tmp pra não ler/escrever o jobs.db real."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.iniciar_db()


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
    from datetime import date
    prov = _Prov(LLMIndisponivel("quota"))
    monkeypatch.setattr(az, "obter_provider", lambda: prov)
    monkeypatch.setattr(az, "carregar_cv", lambda: "CV")
    monkeypatch.setattr("config.ENRICH_MAX_FALHAS_LLM", 2, raising=False)
    jobs = [_job(f"vaga {i}") for i in range(5)]
    analisar_vagas(jobs)
    assert prov.chamadas == 2  # parou após 2 falhas
    assert all(j.analise is None for j in jobs)
    # I3: bateu o teto → latch diário de LLM gravado nos metadados
    assert db.obter_metadado(f"llm_off_{date.today().isoformat()}") == "1"


def test_analisar_vagas_seta_in_place(monkeypatch):
    import enrich.analyze as az
    monkeypatch.setattr(az, "obter_provider", lambda: _Prov(BOM))
    monkeypatch.setattr(az, "carregar_cv", lambda: "CV")
    jobs = [_job()]
    analisar_vagas(jobs)
    assert jobs[0].analise.compat_score == 90


# --- C1: erro não-LLMIndisponivel no enrich NÃO pode subir pro ciclo ---

def test_provider_module_not_found_nao_propaga(monkeypatch):
    import enrich.analyze as az

    def _boom():
        raise ModuleNotFoundError("No module named 'google.genai'")

    monkeypatch.setattr(az, "obter_provider", _boom)
    monkeypatch.setattr(az, "carregar_cv", lambda: "CV real do candidato")
    jobs = [_job("vaga 1"), _job("vaga 2")]
    analisar_vagas(jobs)  # não levanta
    assert all(j.analise is None for j in jobs)


def test_carregar_cv_oserror_nao_propaga(monkeypatch):
    import enrich.analyze as az
    chamou = {"provider": False}

    def _prov():
        chamou["provider"] = True
        return _Prov(BOM)

    def _cv_boom():
        raise OSError("disco cheio")

    monkeypatch.setattr(az, "obter_provider", _prov)
    monkeypatch.setattr(az, "carregar_cv", _cv_boom)
    jobs = [_job()]
    analisar_vagas(jobs)  # não levanta
    assert jobs[0].analise is None
    assert chamou["provider"] is False  # CV falhou → nem constrói provider


def test_erro_inesperado_por_vaga_nao_derruba_as_outras(monkeypatch):
    import enrich.analyze as az

    class _ProvExplode:
        def __init__(self):
            self.chamadas = 0

        def analisar(self, prompt):
            self.chamadas += 1
            if self.chamadas == 1:
                raise RuntimeError("erro bizarro")
            return BOM

    monkeypatch.setattr(az, "obter_provider", lambda: _ProvExplode())
    monkeypatch.setattr(az, "carregar_cv", lambda: "CV")
    jobs = [_job("a"), _job("b")]
    analisar_vagas(jobs)  # não levanta
    assert jobs[0].analise is None
    assert jobs[1].analise.compat_score == 90


# --- I4: CV vazio → sem análise nenhuma ---

def test_cv_vazio_nao_chama_provider(monkeypatch):
    import enrich.analyze as az
    chamou = {"provider": False}
    monkeypatch.setattr(az, "carregar_cv", lambda: "")
    monkeypatch.setattr(az, "obter_provider",
                        lambda: chamou.__setitem__("provider", True) or _Prov(BOM))
    jobs = [_job()]
    analisar_vagas(jobs)
    assert chamou["provider"] is False
    assert jobs[0].analise is None


# --- I3: latch diário de LLM ---

def test_latch_diario_curto_circuita(monkeypatch):
    import enrich.analyze as az
    from datetime import date

    db.definir_metadado(f"llm_off_{date.today().isoformat()}", "1")

    def _prov_nunca():
        raise AssertionError("provider não devia ser construído com latch ativo")

    monkeypatch.setattr(az, "obter_provider", _prov_nunca)
    monkeypatch.setattr(az, "carregar_cv", lambda: "CV")
    jobs = [_job()]
    analisar_vagas(jobs)  # não levanta
    assert jobs[0].analise is None
