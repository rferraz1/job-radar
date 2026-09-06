import os
import re
from functools import lru_cache
from html.parser import HTMLParser

from logger import get_logger

logger = get_logger()


class _TextoDeHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self._ignorar = False
        self.partes: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._ignorar = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._ignorar = False

    def handle_data(self, data):
        if not self._ignorar and data.strip():
            self.partes.append(data.strip())


@lru_cache(maxsize=8)
def _ler(path: str) -> str:
    if not os.path.exists(path):
        logger.warning(f"[baseline] CV não encontrado em {path} — análise vai rodar sem baseline.")
        return ""
    bruto = open(path, encoding="utf-8", errors="replace").read()
    if path.lower().endswith((".html", ".htm")):
        p = _TextoDeHTML()
        p.feed(bruto)
        texto = "\n".join(p.partes)
    else:
        texto = bruto
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def carregar_cv(path: str | None = None) -> str:
    from config import CV_PATH
    return _ler(os.path.abspath(path or CV_PATH))
