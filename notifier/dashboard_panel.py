"""Publica o painel "Vagas" no dashboard do monorepo de agentes.

O job-radar é standalone, mas quando roda local (launchd) com `--dashboard` ele
escreve um painel JSON em `<AGENTES_DIR>/data/paineis/vagas.json` e dispara o
`core.dashboard.publicar` do repo `agentes` — assim o radar de vagas aparece na
mesma página que o agente de Candidaturas.

Nada aqui levanta: qualquer falha é logada e o ciclo do job-radar segue.
"""

import json
import os
import subprocess
from datetime import datetime

from database.database import _conectar
from logger import get_logger

logger = get_logger()

AGENTES_DIR = os.path.expanduser(os.getenv("AGENTES_DIR", "~/git/agentes"))
_PAINEL_DIR = os.path.join(AGENTES_DIR, "data", "paineis")
_PY = os.path.join(AGENTES_DIR, ".venv", "bin", "python")
_MAX_ITENS = 40
_JANELA_DIAS = 3


def _vagas_recentes(perfil_chave: str) -> list[tuple]:
    """Vagas do perfil analisadas nos últimos dias, melhor score primeiro.
    Só as que têm análise LLM — o painel é o "radar", não a fila crua."""
    with _conectar() as conn:
        cur = conn.execute(
            """
            SELECT titulo, empresa, link, relevancia, exploratoria,
                   compat_score, analise_json
            FROM vagas_vistas
            WHERE perfil = ?
              AND analise_json IS NOT NULL
              AND encontrada_em >= datetime('now', ?)
            ORDER BY COALESCE(compat_score, relevancia * 10) DESC, encontrada_em DESC
            """,
            (perfil_chave, f"-{_JANELA_DIAS} days"),
        )
        return cur.fetchall()


def _salario(analise: dict) -> str:
    s = analise.get("salary_estimate") or {}
    lo, hi = s.get("min"), s.get("max")
    if lo is not None and hi is not None:
        return f"R$ {lo}–{hi}"
    if lo is not None:
        return f"R$ {lo}+"
    return "salário n/d"


def _corpo(analise: dict) -> str | None:
    partes = []
    razao = (analise.get("verdict_reason") or "").strip()
    if razao:
        partes.append(razao)
    gaps = [
        g for g in (analise.get("gaps") or [])
        if isinstance(g, dict) and g.get("requisito")
    ]
    if gaps:
        partes.append("Lacunas:")
        for g in gaps:
            sev = g.get("severidade", "?")
            parc = " (tenho parcial)" if g.get("tenho_parcial") else ""
            partes.append(f"  • [{sev}] {g['requisito']}{parc}")
    return "\n".join(partes) if partes else None


def _item(linha: tuple) -> dict:
    titulo, empresa, link, relevancia, exploratoria, compat_score, analise_json = linha
    try:
        analise = json.loads(analise_json) if analise_json else {}
    except (TypeError, ValueError):
        analise = {}

    score = compat_score if compat_score is not None else analise.get("compat_score")
    verdict = analise.get("verdict") or ""
    tag_score = f"{score}%" if score is not None else "sem análise"
    detalhe = " · ".join(
        p for p in (tag_score, _salario(analise) if analise else "", verdict) if p
    )
    marca = "🧭 " if exploratoria else ""
    return {
        "titulo": f"{marca}{titulo} — {empresa or '—'}",
        "detalhe": detalhe or None,
        "link": link or None,
        "corpo": _corpo(analise),
    }


def _ordenar(linhas: list[tuple]) -> list[tuple]:
    def chave(l):
        compat = l[5]
        relevancia = l[3] or 0
        return -(compat if compat is not None else relevancia * 10)
    return sorted(linhas, key=chave)


def publicar_painel(perfis_chaves: list[str]) -> bool:
    """Monta o painel a partir da fila digest-pendente dos perfis rodados e
    publica no dashboard do repo `agentes`. Best-effort — devolve False sem
    levantar se algo falhar."""
    try:
        linhas: list[tuple] = []
        for chave in perfis_chaves:
            try:
                linhas.extend(_vagas_recentes(chave))
            except Exception as e:
                logger.warning(f"[dashboard] fila do perfil {chave} falhou: {type(e).__name__}")

        vistos = set()
        unicas = []
        for l in _ordenar(linhas):
            k = (l[0], l[1])
            if k in vistos:
                continue
            vistos.add(k)
            unicas.append(l)
        unicas = unicas[:_MAX_ITENS]

        itens = [_item(l) for l in unicas]
        grupos = [{"titulo": f"🎯 Vagas no radar ({len(itens)})", "itens": itens}] if itens else []
        painel = {
            "id": "vagas",
            "titulo": "Vagas",
            "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
            "resumo": (
                f"{len(itens)} vaga(s) nos últimos {_JANELA_DIAS} dias · perfis: {', '.join(perfis_chaves)}"
                if itens else f"nenhuma vaga analisada nos últimos {_JANELA_DIAS} dias"
            ),
            "grupos": grupos,
        }

        os.makedirs(_PAINEL_DIR, exist_ok=True)
        destino = os.path.join(_PAINEL_DIR, "vagas.json")
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(painel, f, ensure_ascii=False, indent=2)
            f.write("\n")
        logger.info(f"[dashboard] painel de vagas escrito: {len(itens)} item(ns).")

        if not os.path.exists(_PY):
            logger.warning(f"[dashboard] venv do agentes não encontrado em {_PY} — painel escrito, sem publicar.")
            return False
        r = subprocess.run(
            [_PY, "-m", "core.dashboard", "--publicar"],
            cwd=AGENTES_DIR, capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            logger.warning(f"[dashboard] publicar retornou {r.returncode}.")
            return False
        logger.info("[dashboard] dashboard publicado.")
        return True
    except Exception as e:
        logger.error(f"[dashboard] publicar_painel falhou: {type(e).__name__}: {e}")
        return False
