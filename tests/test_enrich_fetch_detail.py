from enrich.fetch_detail import buscar_descricao
from job import Job


def _job(**kw):
    base = dict(titulo="X", empresa="Y", local="Z", link="http://x/1", site="Gupy")
    base.update(kw)
    return Job(**base)


def test_usa_descricao_ja_presente(monkeypatch):
    j = _job(site="Greenhouse")
    j.descricao = "Texto completo da vaga do Greenhouse."
    texto, completo = buscar_descricao(j)
    assert texto == "Texto completo da vaga do Greenhouse."
    assert completo is True


def test_fetch_http_ok(monkeypatch):
    import enrich.fetch_detail as fd
    monkeypatch.setattr(fd, "_get_html", lambda url: (
        "<html><body><main>"
        "Buscamos uma pessoa Desenvolvedora Júnior para atuar com Python e SQL no time de dados. "
        "Responsabilidades: manutenção de pipelines, criação de relatórios, suporte a análises. "
        "Requisitos: experiência com Python, noções de SQL, vontade de aprender. "
        "Oferecemos: vale-refeição, plano de saúde, home office."
        "</main></body></html>"
    ))
    texto, completo = buscar_descricao(_job())
    assert "Buscamos uma pessoa Desenvolvedora Júnior" in texto
    assert completo is True


def test_texto_curto_cai_no_fallback(monkeypatch):
    import enrich.fetch_detail as fd
    # HTML que resulta em ~50 chars (acima do fallback mas abaixo de 200)
    monkeypatch.setattr(fd, "_get_html", lambda url: (
        "<html><body><main>"
        "Vaga para Desenvolvedor com experiência em Python. Envie seu currículo."
        "</main></body></html>"
    ))
    j = _job()
    j.descricao = ""
    texto, completo = buscar_descricao(j)
    assert j.titulo in texto and j.empresa in texto
    assert completo is False


def test_falha_cai_no_fallback_card(monkeypatch):
    import enrich.fetch_detail as fd
    monkeypatch.setattr(fd, "_get_html", lambda url: (_ for _ in ()).throw(ConnectionError()))
    j = _job()
    j.descricao = ""
    texto, completo = buscar_descricao(j)
    assert j.titulo in texto and j.empresa in texto
    assert completo is False
