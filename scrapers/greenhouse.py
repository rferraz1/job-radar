import re
from html.parser import HTMLParser

import requests

from config import GREENHOUSE_BOARDS
from job import Job, _normalizar
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
_TIMEOUT = 20


class _Texto(HTMLParser):
    def __init__(self):
        super().__init__()
        self.p: list[str] = []

    def handle_data(self, data):
        if data.strip():
            self.p.append(data.strip())


def _html_para_texto(html: str) -> str:
    import html as _h
    t = _Texto()
    t.feed(_h.unescape(html or ""))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(t.p)).strip()


def _get_jobs(board: str) -> list[dict]:
    r = requests.get(_API.format(board=board), timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json().get("jobs", [])


class GreenhouseScraper(BaseScraper):
    """Boards públicos do Greenhouse (boards-api.greenhouse.io). Precisa da
    lista GREENHOUSE_BOARDS (slugs de empresa). A API traz a descrição inteira
    (`content=true`), então essas vagas pulam o fetch_detail do estágio 2."""

    def __init__(self, termos_busca: list[str]):
        self.termos = [_normalizar(t) for t in termos_busca]

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for board in GREENHOUSE_BOARDS:
            try:
                jobs = _get_jobs(board)
            except Exception as e:
                logger.warning(f"[Greenhouse] board '{board}' falhou: {type(e).__name__}: {e}")
                continue
            for j in jobs:
                titulo = (j.get("title") or "").strip()
                titulo_norm = _normalizar(titulo)
                if not any(t in titulo_norm for t in self.termos):
                    continue
                vaga = Job(
                    titulo=titulo,
                    empresa=board,
                    local=(j.get("location") or {}).get("name", "Não informado"),
                    link=j.get("absolute_url", ""),
                    site="Greenhouse",
                    publicado_em=(j.get("updated_at") or "")[:10],
                )
                vaga.descricao = _html_para_texto(j.get("content", ""))
                vagas.append(vaga)
        logger.info(f"[Greenhouse] {len(vagas)} vaga(s) de {len(GREENHOUSE_BOARDS)} board(s)")
        return vagas
