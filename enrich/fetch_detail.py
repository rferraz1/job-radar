import re
from html.parser import HTMLParser

import requests

from logger import get_logger

logger = get_logger()

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_TIMEOUT = 20


class _TextoDeHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip = 0
        self.partes: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.partes.append(data.strip())


def _get_html(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.text


def _texto_limpo(html: str) -> str:
    p = _TextoDeHTML()
    p.feed(html)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(p.partes)).strip()


def _fallback_card(job) -> str:
    return f"{job.titulo}\n{job.empresa}\n{job.local}\nModalidade: {job.modalidade or 'n/d'}"


def buscar_descricao(job) -> tuple[str, bool]:
    ja = getattr(job, "descricao", "") or ""
    if ja.strip():
        return ja.strip(), True
    try:
        html = _get_html(job.link)
        texto = _texto_limpo(html)
        if len(texto) >= 20:
            return texto, True
        logger.warning(f"[fetch_detail] descrição curta demais ({len(texto)}) em {job.link} — fallback")
    except Exception as e:
        logger.warning(f"[fetch_detail] falha em {job.link}: {type(e).__name__}: {e} — fallback")
    return _fallback_card(job), False
