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


def test_novas_do_ciclo_colapsa_duplicata_intra_ciclo(monkeypatch):
    monkeypatch.setattr(main, "ja_vista", lambda v: False)
    a = Job(titulo="A", empresa="E", local="Remoto", link="http://x/a", site="S")
    b_dup = Job(titulo="A", empresa="E", local="Remoto", link="http://x/a", site="S")
    c = Job(titulo="C", empresa="E", local="Remoto", link="http://x/c", site="S")

    novas = main._novas_do_ciclo([a, b_dup, c])

    assert len(novas) == 2
    ids = [v.id for v in novas]
    assert ids.count(a.id) == 1
    assert c.id in ids


def test_novas_do_ciclo_colapsa_por_chave_secundaria(monkeypatch):
    # I2: mesma empresa+título, URLs (e portanto ids) diferentes → mesma
    # chave_secundaria. O set de ids sozinho deixava passar; agora não.
    monkeypatch.setattr(main, "ja_vista", lambda v: False)
    a = Job(titulo="Dev Júnior", empresa="ACME", local="Remoto", link="http://x/a", site="S1")
    b = Job(titulo="Dev Júnior", empresa="ACME", local="Remoto", link="http://y/b", site="S2")
    c = Job(titulo="Outra", empresa="ACME", local="Remoto", link="http://z/c", site="S1")
    assert a.id != b.id and a.chave_secundaria == b.chave_secundaria

    novas = main._novas_do_ciclo([a, b, c])

    assert len(novas) == 2
    chaves = [v.chave_secundaria for v in novas]
    assert chaves.count(a.chave_secundaria) == 1


def test_hint_da_vaga():
    assert main._hint_da_vaga(_job_titulo("DevOps Júnior")) == "platform-devops"
    assert main._hint_da_vaga(_job_titulo("Desenvolvedor React")) == "dev"


def _job_titulo(t):
    return Job(titulo=t, empresa="E", local="Remoto", link=f"http://x/{t}", site="S")
