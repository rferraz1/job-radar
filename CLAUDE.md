# CLAUDE.md

Guia pra trabalhar neste repositório. Agente de "Vagas" — monitora boards de
emprego, filtra/pontua por fit, publica no mesmo dashboard do repo
`~/git/agentes` (repo irmão, não submodule — ver "Integração" abaixo).

## Comandos

Ciclo único (perfil obrigatório):
```bash
.venv/bin/python main.py --perfil brasil --once
.venv/bin/python main.py --perfil brasil --once --dashboard   # + publica painel
```
`--perfil` aceita `brasil internacional` (os dois na mesma execução) —
perfis definidos em `perfis.py`. Sem `--once`, roda em loop contínuo
(`INTERVALO_MINUTOS`, usado só em ambiente que não seja launchd/GH Actions).

Testes:
```bash
.venv/bin/python -m pytest -q
```

Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
(usa Playwright — rodar `.venv/bin/playwright install` na primeira vez).
`.env`: `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-flash-latest`).

Achar o link real de uma vaga vista (o log do GitHub Actions só mostra
título + relevância, não a URL):
```bash
sqlite3 data/jobs.db "SELECT titulo, link FROM vagas_vistas WHERE titulo LIKE '%termo%'"
```

## Arquitetura

- **`main.py`** — orquestra: `iniciar_db()` → roda cada scraper por perfil
  (`_rodar_um_ciclo_de_cada`) → filtra (`utils/filtro.py`) → enriquece/pontua
  (`enrich/analyze.py`, LLM com fallback heurístico) → salva
  (`database/database.py`) → digest/notificação → `--dashboard` opcional.
- **`scrapers/`** — um módulo por fonte, todos com uma classe `*Scraper`:
  `linkedin.py`, `gupy.py`, `indeed.py`, `solides.py`, `geekhunter.py`,
  `jobs99.py`, `greenhouse.py`, `catho.py`, `trampos.py` (+ variantes
  `_intl` pro perfil internacional). Scrapers quebram de forma independente
  (bloqueio de anti-bot, mudança de DOM) — checar `data/jobs.db` (funil por
  fonte no log) antes de assumir que "não tem vaga nova" é sinal real.
- **`database/database.py`** — SQLite (`data/jobs.db`), tabela
  `vagas_vistas` é a fonte de verdade de dedup entre ciclos.
- **`enrich/analyze.py`** — pontuação de fit via LLM (Gemini) com fallback
  heurístico se a LLM falhar/latch diário ativo — mesmo padrão de
  `agentes/core/llm`, não é o mesmo código (repos separados).
- **`notifier/`** — `telegram.py` (canal antigo, aposentado — usuário não
  usa Telegram, mas o módulo fica com um `return True` explícito quando não
  configurado, pra não travar o funil que espera "notificação ok" antes de
  marcar vaga como vista); `dashboard_panel.py` (escreve
  `~/git/agentes/data/paineis/vagas.json` e chama
  `<agentes>/.venv/bin/python -m core.dashboard --publicar` via subprocess);
  `alertas.py` (WhatsApp em falha real — duplicado de propósito do
  `agentes/core/alertas.py`, repos/venvs separados, não tentar importar
  entre eles).

## Integração com `agentes`

Este repo é standalone (não faz parte do monorepo `agentes`), mas depende
dele em runtime: `--dashboard` só funciona se `~/git/agentes` existir com
`.venv` instalado (`AGENTES_DIR` env, default `~/git/agentes`). Se o venv
do `agentes` não existir, `dashboard_panel.py` escreve o painel local e
avisa no log — não quebra o ciclo.

## Deploy (launchd, Mac)

`deploy/com.rodolfo.jobradar.plist` → `~/Library/LaunchAgents/`. 6×/dia
(7/10/13/16/19/22h) + `RunAtLoad=true` (roda também no login/wake). Logs em
`/tmp/jobradar.{out,err}.log`. Publish do dashboard herda o gotcha do
`GIT_TERMINAL_PROMPT=0` do `agentes/core/dashboard.py` — ver `CLAUDE.md`
daquele repo se o publish travar/falhar de novo.

## Não fazer

- Não reativar notificação por Telegram sem pedido explícito.
- Não assumir que "0 vaga nova" é sempre real — checar o funil por fonte no
  log antes (scraper pode estar silenciosamente quebrado).
