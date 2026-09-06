import scrapers.greenhouse as gh

PAYLOAD = {
    "jobs": [
        {"id": 1, "title": "DevOps Engineer - Junior", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
         "location": {"name": "Remote - Brazil"}, "content": "<p>Terraform, AWS, Kubernetes. CLT.</p>",
         "updated_at": "2026-09-04T10:00:00-03:00"},
        {"id": 2, "title": "Senior Product Manager", "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
         "location": {"name": "New York"}, "content": "<p>10y experience.</p>", "updated_at": "2026-09-04T10:00:00-03:00"},
    ]
}


def test_filtra_por_termo_e_traz_descricao(monkeypatch):
    monkeypatch.setattr(gh, "GREENHOUSE_BOARDS", ["acme"])
    monkeypatch.setattr(gh, "_get_jobs", lambda board: PAYLOAD["jobs"])
    vagas = gh.GreenhouseScraper(termos_busca=["devops", "developer"]).buscar_vagas()
    assert len(vagas) == 1
    v = vagas[0]
    assert v.titulo == "DevOps Engineer - Junior"
    assert v.site == "Greenhouse"
    assert "Terraform, AWS, Kubernetes" in v.descricao  # HTML limpo
    assert v.link == "https://boards.greenhouse.io/acme/jobs/1"


def test_board_sem_resposta_nao_quebra(monkeypatch):
    monkeypatch.setattr(gh, "GREENHOUSE_BOARDS", ["acme"])
    monkeypatch.setattr(gh, "_get_jobs", lambda board: (_ for _ in ()).throw(ConnectionError()))
    assert gh.GreenhouseScraper(termos_busca=["devops"]).buscar_vagas() == []
