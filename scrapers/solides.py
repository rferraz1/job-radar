
import requests

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

# MEDIDO ao vivo (Claude in Chrome, 06/09): o site trocou a listagem de
# vagas por um SPA Next.js que monta os cards via JS depois de um fetch —
# o seletor DOM antigo ("li:has(h2 a)") não existe mais e o scraper via
# Playwright só dava timeout. O SPA busca de um endpoint JSON público:
#
#   GET https://vagas.solides.com.br/api/vacancies?page=N&take=20&title=<termo>&locations=
#
# Resposta: {"totalPages": int, "currentPage": int, "count": int, "data": [...]}.
# Ir direto no JSON é mais rápido (sem navegador), não tem timeout de
# render e ainda corrige um bug antigo: a URL de antes
# ("/vagas/todos/<termo>") era lida pelo site como title="todos" com o
# termo IGNORADO — o scraper vinha buscando o feed genérico, nunca a
# palavra-chave.
#
# take: o site usa 14; testado até 25 OK, 50 devolve HTTP 500. Fica em 20.
_API_URL = "https://vagas.solides.com.br/api/vacancies"
_TAKE = 20

# Mesmo raciocínio de gupy.py/indeed.py: 3 páginas por termo, equilíbrio
# entre cobertura e custo por ciclo.
MAX_PAGINAS = 3

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# jobType do JSON -> valor canônico do campo Job.modalidade ("" quando a
# fonte não diz). É o sinal real de modalidade da API (o bool `homeOffice`
# do mesmo payload subconta: mede 2 remotas onde jobType mede 6).
_MODALIDADE_POR_JOBTYPE = {
    "remoto": "Remoto",
    "hibrido": "Híbrido",
    "presencial": "Presencial",
}


class SolidesScraper(BaseScraper):
    """Busca vagas no https://vagas.solides.com.br (via API JSON pública)."""

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            vagas.extend(self._buscar_termo(termo))

        logger.info(f"[Solides] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        logger.info(f"[Solides] Buscando: {termo}")
        vagas: list[Job] = []

        for pagina in range(1, MAX_PAGINAS + 1):
            params = {
                "page": pagina,
                "take": _TAKE,
                "title": termo,
                "locations": "",
            }
            try:
                resp = requests.get(
                    _API_URL, params=params, headers=_HEADERS, timeout=30
                )
                resp.raise_for_status()
                payload = resp.json()
            except requests.RequestException as e:
                logger.warning(
                    f"[Solides] Falha na página {pagina} de '{termo}': {e} — "
                    "parando de paginar (pode ter ficado vaga de fora)."
                )
                break
            except ValueError as e:
                logger.warning(f"[Solides] Resposta não-JSON em '{termo}': {e}")
                break

            dados = payload.get("data") or []
            if not dados:
                if pagina == 1:
                    logger.info(f"[Solides] 0 resultados reais para '{termo}'.")
                break

            for item in dados:
                vaga = self._montar_vaga(item)
                if vaga:
                    vagas.append(vaga)

            total_paginas = payload.get("totalPages") or 1
            if pagina >= total_paginas:
                break

        return vagas

    def _montar_vaga(self, item: dict) -> Job | None:
        titulo = (item.get("title") or "").strip()
        vaga_id = item.get("id")
        if not titulo or vaga_id in (None, ""):
            return None

        empresa = (item.get("companyName") or "").strip() or "Não informado"

        # URL pública da vaga: /vagas/<slug>/<id> serve tanto id numérico
        # (916074) quanto hashid ("vgV6ou5UrL"); /vaga/<id> só funciona pro
        # numérico (hashid dá HTTP 500). slug é o slug da empresa, cosmético
        # na rota (a vaga resolve mesmo com slug vazio), mas vem sempre no
        # payload — usar mantém a URL estável entre ciclos (importante pro
        # dedup por hash de link em Job.id).
        slug = (item.get("slug") or "").strip()

        cidade = ((item.get("city") or {}).get("name") or "").strip()
        uf = ((item.get("state") or {}).get("code") or "").strip()
        if cidade and uf:
            local = f"{cidade} - {uf}"
        elif cidade or uf:
            local = cidade or uf
        else:
            local = "Não informado"

        modalidade = _MODALIDADE_POR_JOBTYPE.get(
            (item.get("jobType") or "").strip().lower(), ""
        )

        # createdAt vem como data ISO ("2026-09-04") — formato livre aceito
        # pelo campo (ver docstring de Job.publicado_em).
        publicado_em = (item.get("createdAt") or "").strip()

        return Job(
            titulo=titulo,
            empresa=empresa,
            local=local,
            link=f"https://vagas.solides.com.br/vagas/{slug}/{vaga_id}",
            site="Solides",
            publicado_em=publicado_em,
            modalidade=modalidade,
        )
