import json

import database.database as db
from job import Job
from enrich.models import Analysis


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.iniciar_db()


def _analise(score):
    return Analysis.from_dict({"compat_score": score, "compat_reasoning": "x", "verdict": "avaliar"})


def test_migracao_idempotente(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    # grava algo pra tabela não vir vazia (senão iniciar_db dispara o
    # guarda BancoVazioSuspeito, que é outra proteção, não a migração)
    j = Job(titulo="X", empresa="E", local="R", link="http://x/0", site="S")
    db.salvar_vaga(j, perfil_chave="brasil")
    db.iniciar_db()  # roda de novo, não pode quebrar
    with db._conectar() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(vagas_vistas)")}
    assert {"compat_score", "analise_json"} <= cols


def test_salvar_e_ler_com_analise(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    j = Job(titulo="DevOps Jr", empresa="ACME", local="Remoto", link="http://x/1", site="S")
    j.relevancia = 6
    db.salvar_vaga(j, perfil_chave="brasil", digest_pendente=True, analise=_analise(92))
    linhas = db.obter_vagas_pendentes_digest("brasil")
    assert len(linhas) == 1
    titulo, empresa, link, rel, expl, compat, aj = linhas[0]
    assert compat == 92
    assert json.loads(aj)["compat_score"] == 92


def test_digest_ordena_por_compat_depois_relevancia(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    a = Job(titulo="A", empresa="E", local="R", link="http://x/a", site="S"); a.relevancia = 9
    b = Job(titulo="B", empresa="E", local="R", link="http://x/b", site="S"); b.relevancia = 3
    db.salvar_vaga(a, perfil_chave="brasil", digest_pendente=True)  # sem análise -> 9*10=90
    db.salvar_vaga(b, perfil_chave="brasil", digest_pendente=True, analise=_analise(95))
    linhas = db.obter_vagas_pendentes_digest("brasil")
    assert linhas[0][0] == "B"  # compat 95 > 90
