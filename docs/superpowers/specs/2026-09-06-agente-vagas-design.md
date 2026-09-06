# Agente de Vagas — Design (evolução do JobRadar)

**Data:** 2026-09-06
**Status:** aprovado no brainstorming, aguardando revisão do spec antes do plano de implementação
**Escopo:** primeiro agente de um ecossistema futuro. Este spec cobre SÓ o agente de vagas.

---

## 1. Contexto e decisão

O `rferraz1/job-radar` já existe e funciona: scrapers de LinkedIn (endpoint guest
público, sem login), Gupy, Catho, GeekHunter, Indeed, Solides; dedup por URL +
empresa|título; score heurístico 0–10 (`job.py:combina_com` / `pontuar_relevancia`);
filtro por perfil (`perfis.py`); digest no Telegram; roda hoje via cron do GitHub
Actions.

O pedido do usuário (originado numa conversa com o Codex) descrevia um ecossistema
de agentes com FastAPI + Postgres + orquestrador. **Decisão: caminho híbrido
faseado (opção C).** Fase 1 evolui o JobRadar por dentro e entrega valor já; a
estrutura de serviço/orquestrador nasce na Fase 2, quando existir um 2º agente e um
host 24/7 que justifiquem — YAGNI. "Escalável" aqui significa "não travar a
evolução", não "começar pesado".

**Perfil-alvo:** júnior/estágio dev continua o principal (comprovado, ~17
candidaturas reais). Entra uma trilha nova: as áreas de cloud/infra **com viés de
código** — DevOps júnior, Cloud Engineer Jr, Platform Engineer Jr, a fatia dev de
SRE, e DevSecOps/AppSec. Fica de fora: infra pura de rede, SOC, pentest (longe de
desenvolvimento). Na prática é **um perfil dev com vocabulário expandido**, não dois
perfis paralelos.

---

## 2. O que muda vs. hoje

| Hoje | Depois (Fase 1) |
|---|---|
| Cron do GitHub Actions | **Local no Mac** via launchd, modo "run once" a cada 3h (07h–23h) — mesmo padrão do `workout-generator` |
| 1 perfil "dev júnior" | 1 perfil dev **expandido** (júnior dev + platform/devops/cloud/SRE/devsecops com viés de código) |
| Score heurístico 0–10 → digest de tudo que passa | **Funil 2 estágios:** heurística filtra barato → LLM (Gemini Flash) analisa só as sobreviventes |
| — | **Estimativa de salário** por vaga (LLM) |
| — | **Análise de lacunas** por vaga (LLM): o que a vaga pede que o candidato não tem |
| Digest diário no Telegram | Digest diário **+ alerta imediato** quando compat ≥ limiar (configurável, default 85) |
| LinkedIn/Gupy/Catho/GeekHunter/Indeed/Solides | + **Greenhouse** (API pública de board). Workday → Fase 2 |
| Config espalhada em `config.py` + secrets no GitHub | Config em `runtime/settings.py` a partir de `.env` (gitignored) |

**O que NÃO muda:**
- LinkedIn só via endpoint guest público (sem login, sem Playwright DOM, sem
  anti-bot). Regra fixa do usuário — o perfil de automação já está flagado pelo
  PerimeterX. Nenhuma exceção.
- Greenhouse/Workday são ATS por empresa (mais abertos que o LinkedIn), mas com o
  mesmo cuidado: sem forçar, sem contornar bloqueio.
- SQLite versionado no repo; dedup por URL + empresa|título; Telegram como canal.
- Rodízio de termos por ciclo, cadência alta/baixa por fonte, heartbeat.

---

## 3. Pipeline e fluxo de dados

```
1. SCRAPE          cada fonte → vagas cruas (título, empresa, local, link, modalidade)
        ↓
2. DEDUP           compara com vagas_vistas (hash URL + empresa|título) → só as novas seguem
        ↓
3. FILTRO BARATO   heurística atual (job.py) + vocabulário expandido
   (~500 → ~15)    mata fora-de-área / sênior / local errado. ZERO custo de LLM.
        ↓
4. BUSCAR DETALHE  pras ~15 sobreviventes: baixa a descrição completa da vaga
                   (Greenhouse já traz na API; resto = fetch da página do link)
                   falha → usa texto do card + marca confiança menor
        ↓
5. ANÁLISE LLM     Gemini Flash, 1 chamada por vaga:
   (~15/ciclo)     entra: descrição + CV V3 (cacheado) + dica de trilha
                   sai: { compat 0-100, salário estimado + confiança, lacunas[],
                          strengths[], porquê, veredito }
        ↓
6. ROTEAR          compat ≥ threshold  → alerta IMEDIATO no Telegram (card completo)
                   todas as analisadas → entram no digest diário
        ↓
7. GRAVAR          vagas_vistas += vaga + JSON da análise
                   re-run não re-analisa; histórico serve pra calibrar o threshold
```

### Passo novo relevante: buscar detalhe (4)

Hoje os scrapers só extraem título/empresa/local do card de busca. A análise LLM
precisa da **descrição completa**. O passo 4 roda só nas ~15 que passaram o filtro
barato — nunca nas 500 cruas. Fontes que já entregam descrição no resultado de
busca (Greenhouse) pulam o fetch.

### Estimativa de volume e custo

- ~4 ciclos/dia × ~15 análises = ~60 chamadas LLM/dia, ~1.800/mês.
- Gemini Flash free tier: ~1.500 req/**dia**, 1M tokens/min. Folga enorme.
- Input ~4k tokens (descrição + CV), output ~800 tokens.
- **Custo Fase 1: R$ 0/mês.** GitHub Actions sai de cena (roda local). SQLite no
  repo. Telegram grátis.
- Se um dia trocar Gemini → Claude API: ~US$ 3–4/mês (Haiku), ~US$ 11/mês (Sonnet).

---

## 4. Estrutura de módulos

Evolução do repo atual, sem reorg big-bang. Novo em **negrito**.

```
job-radar/
  config.py                    # + vocabulário cloud/devops (KEYWORDS_CARGO_*, QUALIFICADORES_*)
  perfis.py                    # perfil dev expandido (não um perfil novo separado)
  job.py                       # Job model + heurística (combina_com) — função pura, sem I/O
  main.py                      # orquestra o ciclo; ganha os passos 4–7
  logger.py

  scrapers/
    base.py + existentes
    greenhouse.py              # NOVO — boards-api.greenhouse.io, precisa de lista de empresas

  enrich/                      # NOVO — estágios 4 e 5
    __init__.py
    fetch_detail.py            # baixa descrição completa a partir do link
    analyze.py                 # orquestra a análise — agnóstico de provedor
    prompt.py                  # template do prompt de análise
    models.py                  # dataclass Analysis (ver seção 5)
    providers/
      base.py                  # interface LLMProvider: analyze(job, cv, hint) -> Analysis
      gemini.py                # implementação Gemini Flash
      # anthropic.py           # Fase futura — drop-in, sem mexer no resto

  notifier/
    telegram.py                # + formato "alerta imediato" (card rico)
    digest.py                  # NOVO — monta o digest diário (sai do main.py)

  storage/                     # NOVO — formaliza o que hoje é ad-hoc
    db.py                      # único lugar que toca SQLite; vagas_vistas + coluna/tabela de análise
    baseline.py                # carrega o texto do CV V3 (claude-context/curriculo/ ou CV_PATH)

  runtime/                     # NOVO — adaptadores de deploy; VM-readiness mora aqui
    run_once.py                # entrypoint: 1 ciclo completo e sai
    settings.py                # config por env/.env — nada hardcoded

  deploy/
    com.rodolfo.jobradar.plist # launchd (Mac) — usar agora
    jobradar.service           # systemd (VM) — pronto, parado
    README.md                  # checklist de migração Mac → VM

  docs/superpowers/specs/2026-09-06-agente-vagas-design.md   # este arquivo
  tests/                       # + testes dos módulos novos
```

### Fronteiras (o que cada unidade faz, como se usa, do que depende)

- **`scrapers/`** — "me dá vagas cruas pra estes termos". Não sabe de filtro, LLM
  nem notificação. Depende de: rede, Playwright (só onde necessário), `job.Job`.
- **`job.py` (heurística)** — "esta vaga crua passa a barra barata?". Função pura,
  sem I/O. Depende de: `config` (listas de palavras).
- **`enrich/fetch_detail.py`** — "me dá o texto completo desta vaga". Depende de:
  rede. Isola o "como cada fonte expõe a descrição".
- **`enrich/analyze.py`** — "dada uma vaga + CV, me dá uma Analysis". Não sabe qual
  LLM. Depende de: um `providers/*`.
- **`enrich/providers/gemini.py`** — o único que sabe de Gemini (endpoint, chave,
  formato). Trocar de provedor = trocar `LLM_PROVIDER` no `.env`.
- **`notifier/`** — "envia isto". Não decide o que vale enviar.
- **`storage/db.py`** — o único que toca SQLite. Migração pra Postgres = trocar só
  este arquivo.
- **`runtime/`** — o único que sabe "estamos num Mac via launchd". Migração pra VM
  = novo arquivo systemd + o mesmo `run_once`.

---

## 5. Contrato da análise LLM

### Entrada (para o provider)

- `job`: título, empresa, local, modalidade, senioridade estimada, descrição
  completa (ou texto do card + flag `descricao_parcial=True`).
- `cv_text`: texto puro do CV V3. Estático — cacheado entre chamadas.
- `hint`: dica de trilha (`dev` | `platform-devops`) pra o modelo pesar certo.

### Saída — dataclass `Analysis`, o modelo DEVE devolver este JSON

```json
{
  "compat_score": 0,
  "compat_reasoning": "2-3 frases: por que este score",
  "salary_estimate": {
    "min": null,
    "max": null,
    "moeda": "BRL",
    "periodo": "mes",
    "confianca": "alta | media | baixa",
    "base": "de onde inferiu (faixa no anúncio / típica do cargo+senioridade / mercado)"
  },
  "gaps": [
    { "requisito": "...", "severidade": "bloqueante | importante | menor", "tenho_parcial": false }
  ],
  "strengths": [ "requisito batido / projeto relevante do CV" ],
  "verdict": "candidatar | avaliar | pular",
  "verdict_reason": "uma linha"
}
```

### Regras do prompt

- Honesto, sem inflar. É melhor um score baixo correto que um alto otimista.
- Gap **bloqueante** (ex: "inglês fluente obrigatório", "5+ anos de experiência",
  "graduação completa exigida") derruba o `compat_score` pra faixa baixa
  independente de quão bem as skills batem.
- Salário: só estima `min`/`max` com base real. Sem base → `null` + `confianca:
  baixa` + `base: "faixa típica do cargo/senioridade"`.
- `verdict` reflete o conjunto (score + gaps + fit da transição de carreira), não
  só o número.

### Validação

- JSON malformado ou score fora de 0–100 → 1 retry com instrução mais estrita.
- Ainda ruim → cai pro score heurístico, loga o evento, vaga entra no digest
  (nunca no alerta imediato).

---

## 6. Agendamento e prontidão pra VM

### Agora (Mac)

- `runtime/run_once.py` = entrypoint. Faz 1 ciclo completo e sai.
- `deploy/com.rodolfo.jobradar.plist` roda o entrypoint a cada 3h, 07h–23h.
  Instalação e regra de "não reiniciar à toa" documentadas em `deploy/README.md`
  (mesma disciplina do `workout-generator`).
- `runtime/settings.py` lê tudo de `.env` (gitignored):
  `JOBRADAR_DB_PATH`, `JOBRADAR_THRESHOLD` (default 85), `LLM_PROVIDER`
  (default `gemini`), `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
  `CV_PATH`.
- Nada de `/Users/rodolfoferraz/...` hardcoded em lugar nenhum.

### VM depois

- Clona o repo, `pip install -r requirements.txt`, cria o mesmo `.env`,
  `cp deploy/jobradar.service /etc/systemd/system/` (com timer ou loop
  controlado), `systemctl enable --now`. Pronto.
- SQLite → Postgres só se concorrência passar a importar. `storage/db.py` é o
  único arquivo a trocar.

---

## 7. Tratamento de erro (resumo)

| Falha | Comportamento |
|---|---|
| Uma fonte cai | loga, segue com as outras (já faz hoje) |
| Fetch de detalhe falha | usa texto do card, `descricao_parcial=True`, analisa mesmo assim |
| LLM falha / rate-limit | retry com backoff; se persistir, vaga volta pra fila do próximo ciclo, entra no digest com score heurístico |
| Limite diário do Gemini free estourado | para o LLM, resto do dia é só heurística, retoma no dia seguinte |
| JSON de análise inválido | ver seção 5 (retry → heurística) |

---

## 8. Testes

- **`job.py` heurística** — já tem `tests/test_filtro.py`. Estender com casos da
  trilha cloud/devops (DevOps Jr passa, "Senior SRE" reprova, "Analista de Redes"
  fora).
- **`scrapers/greenhouse.py`** — teste do parse do JSON da API (payload real
  reduzido, sem rede), padrão do `tests/test_solides.py`.
- **`enrich/analyze.py`** — mock do provider: valida que JSON malformado cai pra
  heurística; que score fora de range dispara retry.
- **`enrich/providers/gemini.py`** — teste de contrato: dado um payload de resposta
  do Gemini, produz uma `Analysis` válida.
- **`notifier/digest.py`** — dado um conjunto de vagas+análises, o texto do digest
  sai correto (função pura).
- Sem teste que chame o Gemini de verdade no CI.

---

## 9. Explicitamente Fase 2 — NÃO construir agora

- Serviço FastAPI / API HTTP.
- Postgres.
- Supervisor / orquestrador de agentes.
- Os outros 4 agentes (e-mail, dev, personal trainer, carreira).
- Scraping de Workday.
- Dashboard web (o artifact "Radar de Candidaturas" segue manual).
- Provider Anthropic (a interface fica pronta; a implementação entra quando/se o
  usuário quiser pagar API).

---

## 10. Ordem de implementação sugerida (para o plano)

1. `runtime/settings.py` + `.env.example` + `storage/db.py` (formaliza o acesso ao
   SQLite atual, sem mudar schema ainda).
2. `storage/baseline.py` (carregar CV V3).
3. Vocabulário cloud/devops em `config.py` + casos em `tests/test_filtro.py`.
4. `enrich/models.py` + `enrich/providers/base.py` + `enrich/providers/gemini.py`
   + `enrich/prompt.py` + testes com mock.
5. `enrich/fetch_detail.py` + testes.
6. `enrich/analyze.py` (junta 4+5) + fallback heurístico + testes.
7. Schema de análise em `storage/db.py` (coluna/tabela nova em `vagas_vistas`).
8. `notifier/digest.py` (extrai do `main.py`) + formato de alerta imediato em
   `notifier/telegram.py`.
9. `scrapers/greenhouse.py` + lista inicial de empresas + testes.
10. `runtime/run_once.py` liga tudo; `main.py` passa a delegar.
11. `deploy/` (plist + service + README); instalar o launchd; primeiro ciclo real
    observado.
