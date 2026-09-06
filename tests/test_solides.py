"""Testes da montagem de Job a partir do JSON da API da Sólides
(scrapers/solides.py).

MEDIDO 06/09: a Sólides trocou a listagem por um SPA e o scraper via DOM
(Playwright + seletor "li:has(h2 a)") passou a só dar timeout. O conserto
foi ir direto no endpoint JSON que o próprio SPA consome
(/api/vacancies?...). `_montar_vaga` transforma um dict do payload num Job
— função pura, sem rede/browser, barata de testar e é onde mora o risco de
regressão (mudança de nome de campo no payload, formato de link errado
quebrando o dedup por hash de URL em Job.id).

Os payloads abaixo são recortes reais da resposta da API conferidos ao
vivo, reduzidos aos campos que o scraper lê.
"""

from scrapers.solides import SolidesScraper


def _scraper():
    return SolidesScraper(termos_busca=[])


def test_vaga_completa_id_numerico():
    item = {
        "id": 916074,
        "slug": "bakertilly",
        "title": "Auditor(a) de TI Júnior ",
        "companyName": "BAKER TILLY BRASIL",
        "city": {"name": "Porto Alegre"},
        "state": {"code": "RS"},
        "jobType": "hibrido",
        "createdAt": "2026-09-04",
    }
    vaga = _scraper()._montar_vaga(item)
    assert vaga.titulo == "Auditor(a) de TI Júnior"
    assert vaga.empresa == "BAKER TILLY BRASIL"
    assert vaga.local == "Porto Alegre - RS"
    assert vaga.modalidade == "Híbrido"
    assert vaga.publicado_em == "2026-09-04"
    assert vaga.site == "Solides"
    assert vaga.link == "https://vagas.solides.com.br/vagas/bakertilly/916074"


def test_id_hashid_usa_a_mesma_rota():
    # /vaga/<id> só resolve id numérico (hashid dá HTTP 500); /vagas/<slug>/<id>
    # resolve os dois. Ver comentário em _montar_vaga.
    item = {
        "id": "vgV6ou5UrL",
        "slug": "senff",
        "title": "Desenvolvedor Junior",
        "companyName": "Grupo Senff",
        "city": {"name": "Curitiba"},
        "state": {"code": "PR"},
        "jobType": "remoto",
    }
    vaga = _scraper()._montar_vaga(item)
    assert vaga.link == "https://vagas.solides.com.br/vagas/senff/vgV6ou5UrL"
    assert vaga.modalidade == "Remoto"


def test_jobtype_desconhecido_ou_ausente_vira_modalidade_vazia():
    base = {"id": 1, "slug": "x", "title": "Dev", "companyName": "ACME"}
    assert _scraper()._montar_vaga({**base}).modalidade == ""
    assert _scraper()._montar_vaga({**base, "jobType": "freela"}).modalidade == ""
    assert _scraper()._montar_vaga({**base, "jobType": "PRESENCIAL"}).modalidade == "Presencial"


def test_cidade_ou_uf_ausente_nao_quebra():
    base = {"id": 1, "slug": "x", "title": "Dev", "companyName": "ACME"}
    assert _scraper()._montar_vaga({**base}).local == "Não informado"
    assert _scraper()._montar_vaga(
        {**base, "city": {"name": "Recife"}, "state": {"code": ""}}
    ).local == "Recife"
    assert _scraper()._montar_vaga(
        {**base, "city": {"name": ""}, "state": {"code": "SP"}}
    ).local == "SP"


def test_empresa_ausente_vira_nao_informado():
    vaga = _scraper()._montar_vaga(
        {"id": 1, "slug": "x", "title": "Dev", "companyName": ""}
    )
    assert vaga.empresa == "Não informado"


def test_item_sem_titulo_ou_sem_id_e_descartado():
    s = _scraper()
    assert s._montar_vaga({"id": 1, "slug": "x", "title": "  ", "companyName": "ACME"}) is None
    assert s._montar_vaga({"id": None, "slug": "x", "title": "Dev", "companyName": "ACME"}) is None
    assert s._montar_vaga({"id": "", "slug": "x", "title": "Dev", "companyName": "ACME"}) is None
