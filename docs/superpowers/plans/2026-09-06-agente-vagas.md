# Agente de Vagas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar ao JobRadar uma trilha cloud/devops, análise profunda por LLM (Gemini Flash) que produz % de compatibilidade + salário estimado + análise de lacunas, e alerta imediato acima de um limiar — mantendo o comportamento atual como fallback.

**Architecture:** Funil de 2 estágios. Estágio 1 = a heurística atual (`job.py`), filtra ~500 vagas cruas → ~15 candidatas sem custo. Estágio 2 = novo pacote `enrich/`, roda só nas candidatas novas: busca a descrição completa e chama um provedor LLM agnóstico que devolve um JSON estruturado (`Analysis`). O roteamento em `main.py` passa a usar `compat_score` (0–100) quando há análise, e cai pro `relevancia` heurístico (0–10) quando não há. Nada de `runtime/` ou `storage/` novos — `main.py --once` e `database/database.py` já cobrem isso (ver "Desvios do spec").

**Tech Stack:** Python 3.11+, `google-genai` (Gemini), `requests`, `playwright` (só onde já usado), `sqlite3`, `python-dotenv` (já presente), `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-06-agente-vagas-design.md`

## Global Constraints

- **LinkedIn:** só endpoint guest público. Nunca login, Playwright DOM de perfil, ou técnica anti-bot. Nenhuma exceção.
- **Custo:** Fase 1 = R$ 0/mês. `LLM_PROVIDER` default `gemini` (free tier). Código agnóstico de provedor.
- **Fallback obrigatório:** se a análise LLM falhar/indisponível, o sistema volta ao comportamento de hoje (routing por `relevancia >= LIMIAR_DIGEST_IMEDIATO`). Nunca perde vaga por causa do LLM.
- **Migrações de schema:** só `ALTER TABLE ADD COLUMN` idempotente, padrão `_garantir_coluna_*` em `database/database.py`. Nunca `DROP`/recriar.
- **Baseline do candidato:** CV V3, caminho em `CV_PATH` (default aponta pro `curriculo.html` do checkout de `claude-context`).
- **Segredos:** só via `.env` (gitignored) / env vars. Nunca commitados. `.env.example` documenta as chaves sem valores.
- **Honestidade da análise:** o prompt instrui score realista; gap "bloqueante" (inglês fluente obrigatório, "5+ anos", graduação exigida) derruba `compat_score` pra faixa baixa independente de skill match.

## Desvios do spec

O spec (seção 4) propôs pacotes novos `runtime/` (com `run_once.py`, `settings.py`) e `storage/` (com `db.py`). **Não vão ser criados** — foram propostos antes da leitura completa de `main.py`:

- `main.py` já tem `--once` (1 ciclo e sai) — é o que o launchd chama. Não precisa de `runtime/run_once.py`.
- `config.py` já faz `load_dotenv()` e lê `os.getenv(...)`. Config nova entra lá. Não precisa de `runtime/settings.py`.
- `database/database.py` já é o único módulo que toca SQLite, com migrações incrementais. Não precisa de `storage/db.py`.

O que o spec pediu como intenção (config por `.env`, um entrypoint "run once", acesso a DB isolado) **já existe** — o plano usa o que está lá. Só `enrich/`, `scrapers/greenhouse.py` e `deploy/` são pacotes/arquivos genuinamente novos.

---

## Task 1: Config e dependências

**Files:**
- Modify: `config.py` (adicionar no bloco de env vars, perto da linha 252–275)
- Modify: `requirements.txt`
- Create: `.env.example`
- Modify: `.gitignore` (garantir `.env`)
- Test: `tests/test_config_enrich.py`

**Interfaces:**
- Produces: `config.LLM_PROVIDER: str`, `config.GEMINI_API_KEY: str`, `config.LIMIAR_COMPAT_IMEDIATO: int`, `config.CV_PATH: str`, `config.GREENHOUSE_BOARDS: list[str]`, `config.ENRICH_MAX_FALHAS_LLM: int`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_enrich.py
import importlib


def test_config_enrich_defaults(monkeypatch):
    for var in ("LLM_PROVIDER", "GEMINI_API_KEY", "LIMIAR_COMPAT_IMEDIATO", "CV_PATH"):
        monkeypatch.delenv(var, raising=False)
    import config
    importlib.reload(config)
    assert config.LLM_PROVIDER == "gemini"
    assert config.GEMINI_API_KEY == ""
    assert config.LIMIAR_COMPAT_IMEDIATO == 85
    assert config.CV_PATH.endswith(".html")
    assert isinstance(config.GREENHOUSE_BOARDS, list)
    assert config.ENRICH_MAX_FALHAS_LLM >= 1


def test_config_enrich_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LIMIAR_COMPAT_IMEDIATO", "70")
    import config
    importlib.reload(config)
    assert config.LLM_PROVIDER == "anthropic"
    assert config.LIMIAR_COMPAT_IMEDIATO == 70
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_enrich.py -v`
Expected: FAIL — `AttributeError: module 'config' has no attribute 'LLM_PROVIDER'`

- [ ] **Step 3: Add config**

```python
# config.py — junto do bloco de os.getenv existente (~linha 252)

# --- Análise profunda por LLM (estágio 2 do funil — ver docs/.../specs) ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Compatibilidade (0-100) a partir da qual a vaga vira alerta IMEDIATO.
# Diferente de LIMIAR_DIGEST_IMEDIATO (0-10, heurístico) — este é o score do LLM.
LIMIAR_COMPAT_IMEDIATO = int(os.getenv("LIMIAR_COMPAT_IMEDIATO", 85))
# CV do candidato, usado como baseline pela análise. Default: checkout do
# claude-context ao lado deste repo.
CV_PATH = os.getenv(
    "CV_PATH",
    os.path.join(os.path.dirname(__file__), "..", "claude-context", "curriculo", "curriculo.html"),
)
# Boards públicos do Greenhouse a vigiar (slug da empresa em boards.greenhouse.io/<slug>).
GREENHOUSE_BOARDS = [
    b.strip() for b in os.getenv("GREENHOUSE_BOARDS", "").split(",") if b.strip()
]
# Depois de N falhas seguidas do LLM num ciclo (rate-limit, timeout), para de
# chamar e deixa o resto do ciclo cair no fallback heurístico.
ENRICH_MAX_FALHAS_LLM = int(os.getenv("ENRICH_MAX_FALHAS_LLM", 3))
```

```
# requirements.txt — adicionar
google-genai==0.8.0
```

```
# .env.example (novo arquivo)
# Copie para .env e preencha. .env NÃO vai pro git.
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
LLM_PROVIDER=gemini
GEMINI_API_KEY=
LIMIAR_COMPAT_IMEDIATO=85
CV_PATH=../claude-context/curriculo/curriculo.html
GREENHOUSE_BOARDS=
INTERVALO_MINUTOS=180
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_config_enrich.py -v && pip install -r requirements.txt`
Expected: PASS; `google-genai` instala

- [ ] **Step 5: Commit**

```bash
git add config.py requirements.txt .env.example .gitignore tests/test_config_enrich.py
git commit -m "feat(enrich): config e dependências pra análise LLM"
```

---

## Task 2: `enrich/models.py` — dataclass `Analysis`

**Files:**
- Create: `enrich/__init__.py` (vazio)
- Create: `enrich/models.py`
- Test: `tests/test_enrich_models.py`

**Interfaces:**
- Produces: `enrich.models.Analysis` (dataclass), `Analysis.from_dict(d: dict) -> Analysis` (valida/clampa; levanta `ValueError` se irrecuperável), `Analysis.to_json() -> str`, `Analysis.resumo_curto() -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrich_models.py
import pytest
from enrich.models import Analysis

VALIDO = {
    "compat_score": 88,
    "compat_reasoning": "Stack Node/React bate; transição de carreira coerente.",
    "salary_estimate": {"min": 3000, "max": 4500, "moeda": "BRL", "periodo": "mes",
                        "confianca": "media", "base": "faixa típica de júnior remoto"},
    "gaps": [{"requisito": "Kubernetes", "severidade": "importante", "tenho_parcial": False}],
    "strengths": ["Projetos reais de RAG/agentes"],
    "verdict": "candidatar",
    "verdict_reason": "Bom fit, sem gap bloqueante.",
}


def test_from_dict_valido():
    a = Analysis.from_dict(VALIDO)
    assert a.compat_score == 88
    assert a.salary_estimate.min == 3000
    assert a.gaps[0].severidade == "importante"
    assert a.verdict == "candidatar"


def test_score_fora_de_range_e_clampado():
    a = Analysis.from_dict({**VALIDO, "compat_score": 140})
    assert a.compat_score == 100
    a2 = Analysis.from_dict({**VALIDO, "compat_score": -5})
    assert a2.compat_score == 0


def test_campos_faltando_levanta():
    with pytest.raises(ValueError):
        Analysis.from_dict({"compat_score": 50})  # sem verdict etc.


def test_verdict_invalido_vira_avaliar():
    a = Analysis.from_dict({**VALIDO, "verdict": "talvez"})
    assert a.verdict == "avaliar"


def test_roundtrip_json():
    a = Analysis.from_dict(VALIDO)
    b = Analysis.from_dict(__import__("json").loads(a.to_json()))
    assert b.compat_score == a.compat_score
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_enrich_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'enrich'`

- [ ] **Step 3: Implement**

```python
# enrich/models.py
import json
from dataclasses import dataclass, field, asdict

_VERDICTS = {"candidatar", "avaliar", "pular"}
_SEVERIDADES = {"bloqueante", "importante", "menor"}
_CONFIANCAS = {"alta", "media", "baixa"}


@dataclass
class SalaryEstimate:
    min: int | None = None
    max: int | None = None
    moeda: str = "BRL"
    periodo: str = "mes"
    confianca: str = "baixa"
    base: str = ""

    @classmethod
    def from_dict(cls, d: dict | None) -> "SalaryEstimate":
        d = d or {}
        conf = str(d.get("confianca", "baixa")).lower()
        return cls(
            min=_int_ou_none(d.get("min")),
            max=_int_ou_none(d.get("max")),
            moeda=str(d.get("moeda", "BRL")),
            periodo=str(d.get("periodo", "mes")),
            confianca=conf if conf in _CONFIANCAS else "baixa",
            base=str(d.get("base", "")),
        )


@dataclass
class Gap:
    requisito: str
    severidade: str = "importante"
    tenho_parcial: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "Gap":
        sev = str(d.get("severidade", "importante")).lower()
        return cls(
            requisito=str(d.get("requisito", "")).strip(),
            severidade=sev if sev in _SEVERIDADES else "importante",
            tenho_parcial=bool(d.get("tenho_parcial", False)),
        )


@dataclass
class Analysis:
    compat_score: int
    compat_reasoning: str
    salary_estimate: SalaryEstimate
    gaps: list[Gap] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    verdict: str = "avaliar"
    verdict_reason: str = ""
    descricao_parcial: bool = False  # True quando a análise usou só o texto do card

    @classmethod
    def from_dict(cls, d: dict) -> "Analysis":
        obrigatorios = ("compat_score", "compat_reasoning", "verdict")
        faltando = [k for k in obrigatorios if k not in d]
        if faltando:
            raise ValueError(f"Analysis.from_dict: campos faltando: {faltando}")
        try:
            score = int(round(float(d["compat_score"])))
        except (TypeError, ValueError):
            raise ValueError(f"compat_score não numérico: {d['compat_score']!r}")
        score = max(0, min(100, score))
        verdict = str(d["verdict"]).lower().strip()
        return cls(
            compat_score=score,
            compat_reasoning=str(d["compat_reasoning"]).strip(),
            salary_estimate=SalaryEstimate.from_dict(d.get("salary_estimate")),
            gaps=[Gap.from_dict(g) for g in (d.get("gaps") or []) if isinstance(g, dict)],
            strengths=[str(s).strip() for s in (d.get("strengths") or []) if str(s).strip()],
            verdict=verdict if verdict in _VERDICTS else "avaliar",
            verdict_reason=str(d.get("verdict_reason", "")).strip(),
            descricao_parcial=bool(d.get("descricao_parcial", False)),
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def resumo_curto(self) -> str:
        s = self.salary_estimate
        sal = f"R$ {s.min}–{s.max}" if s.min and s.max else "salário n/d"
        blk = sum(1 for g in self.gaps if g.severidade == "bloqueante")
        return f"{self.compat_score}% · {sal} · {blk} gap(s) bloqueante(s) · {self.verdict}"


def _int_ou_none(v):
    try:
        return int(round(float(v))) if v is not None else None
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_enrich_models.py -v`
Expected: PASS (5 testes)

- [ ] **Step 5: Commit**

```bash
git add enrich/__init__.py enrich/models.py tests/test_enrich_models.py
git commit -m "feat(enrich): dataclass Analysis com validação/clamp"
```

---

## Task 3: `enrich/baseline.py` — carregar o CV

**Files:**
- Create: `enrich/baseline.py`
- Test: `tests/test_enrich_baseline.py`

**Interfaces:**
- Produces: `enrich.baseline.carregar_cv(path: str | None = None) -> str` (texto puro, cacheado por path; string vazia + log de warning se o arquivo não existe)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrich_baseline.py
from enrich.baseline import carregar_cv


def test_carrega_html_limpo(tmp_path):
    f = tmp_path / "cv.html"
    f.write_text("<html><body><h1>Rodolfo</h1><p>Python &amp; Node</p><script>x=1</script></body></html>")
    txt = carregar_cv(str(f))
    assert "Rodolfo" in txt
    assert "Python & Node" in txt
    assert "x=1" not in txt  # script removido


def test_arquivo_inexistente_retorna_vazio(caplog):
    assert carregar_cv("/nao/existe/cv.html") == ""


def test_cacheia_por_path(tmp_path):
    f = tmp_path / "cv.html"
    f.write_text("<body>v1</body>")
    assert "v1" in carregar_cv(str(f))
    f.write_text("<body>v2</body>")
    assert "v1" in carregar_cv(str(f))  # cache — não relê
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_enrich_baseline.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# enrich/baseline.py
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_enrich_baseline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add enrich/baseline.py tests/test_enrich_baseline.py
git commit -m "feat(enrich): carregar CV como baseline (HTML -> texto, cacheado)"
```

---

## Task 4: `enrich/prompt.py` — montar o prompt

**Files:**
- Create: `enrich/prompt.py`
- Test: `tests/test_enrich_prompt.py`

**Interfaces:**
- Consumes: `job.Job` (campos `titulo`, `empresa`, `local`, `modalidade`, `senioridade`)
- Produces: `enrich.prompt.montar_prompt(job, descricao: str, cv_text: str, hint: str = "dev") -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrich_prompt.py
from enrich.prompt import montar_prompt
from job import Job


def _job():
    return Job(titulo="DevOps Júnior", empresa="ACME", local="Recife, PE",
               link="http://x/1", site="Greenhouse", modalidade="Remoto")


def test_prompt_tem_vaga_cv_e_schema():
    p = montar_prompt(_job(), "Descrição: Terraform, AWS, CI/CD.", "CV: Rodolfo, Python, Node.", hint="platform-devops")
    assert "DevOps Júnior" in p and "ACME" in p
    assert "Terraform, AWS" in p
    assert "Rodolfo, Python, Node" in p
    assert "compat_score" in p and "salary_estimate" in p and "gaps" in p
    assert "bloqueante" in p  # instrução sobre gap bloqueante
    assert "JSON" in p


def test_cv_vazio_nao_quebra():
    p = montar_prompt(_job(), "desc", "", hint="dev")
    assert "sem CV" in p.lower() or "não informado" in p.lower()
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_enrich_prompt.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# enrich/prompt.py
_SCHEMA = """{
  "compat_score": <int 0-100>,
  "compat_reasoning": "<2-3 frases>",
  "salary_estimate": {"min": <int|null>, "max": <int|null>, "moeda": "BRL", "periodo": "mes",
                      "confianca": "alta|media|baixa", "base": "<de onde inferiu>"},
  "gaps": [{"requisito": "<texto>", "severidade": "bloqueante|importante|menor", "tenho_parcial": <bool>}],
  "strengths": ["<requisito batido ou projeto do CV>"],
  "verdict": "candidatar|avaliar|pular",
  "verdict_reason": "<uma linha>"
}"""

_INSTRUCOES = """Você avalia o encaixe entre UM candidato e UMA vaga, para uma pessoa em
transição de carreira (ex-personal trainer, ~6 meses de experiência formal em TI, forte em
projetos próprios de Python/JS/GenAI). Trilha alvo: {hint}.

Regras:
- Seja realista. Um score alto otimista é pior que um score baixo correto.
- Gap BLOQUEANTE (inglês fluente obrigatório, "N+ anos de experiência", graduação completa
  exigida, senioridade sênior/especialista) derruba compat_score para faixa baixa (<40),
  não importa quão bem as skills batem.
- salary_estimate: só preencha min/max com base real (faixa no anúncio, ou faixa típica
  clara do cargo+senioridade no Brasil). Sem base: min/max null, confianca "baixa".
- verdict reflete o conjunto (score + gaps + coerência com a transição), não só o número.

Responda SOMENTE com um objeto JSON neste formato, sem texto antes ou depois:
{schema}"""


def montar_prompt(job, descricao: str, cv_text: str, hint: str = "dev") -> str:
    cv = cv_text.strip() or "(sem CV disponível — avalie só pelo título/senioridade da vaga)"
    return (
        _INSTRUCOES.format(hint=hint, schema=_SCHEMA)
        + "\n\n=== VAGA ===\n"
        + f"Título: {job.titulo}\nEmpresa: {job.empresa}\nLocal: {job.local}\n"
        + f"Modalidade: {job.modalidade or 'não informada'}\n"
        + f"Senioridade (estimada do título): {job.senioridade}\n\n"
        + f"Descrição:\n{descricao.strip()[:8000]}\n\n"
        + "=== CANDIDATO (CV) ===\n"
        + cv[:8000]
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_enrich_prompt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add enrich/prompt.py tests/test_enrich_prompt.py
git commit -m "feat(enrich): template do prompt de análise"
```

---

## Task 5: `enrich/providers/` — interface + Gemini

**Files:**
- Create: `enrich/providers/__init__.py` (vazio)
- Create: `enrich/providers/base.py`
- Create: `enrich/providers/gemini.py`
- Create: `enrich/providers/__init__.py` exporta `obter_provider`
- Test: `tests/test_enrich_provider_gemini.py`

**Interfaces:**
- Produces:
  - `enrich.providers.base.LLMProvider` (ABC): `analisar(self, prompt: str) -> dict` — devolve o JSON já parseado; levanta `LLMIndisponivel` em falha dura (rede, auth, rate-limit) e `LLMRespostaInvalida` se não conseguir JSON válido após 1 retry.
  - `enrich.providers.base.LLMIndisponivel`, `enrich.providers.base.LLMRespostaInvalida` (exceptions)
  - `enrich.providers.obter_provider(nome: str | None = None) -> LLMProvider` — factory a partir de `config.LLM_PROVIDER`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrich_provider_gemini.py
import json
import pytest
from enrich.providers.base import LLMRespostaInvalida, LLMIndisponivel
from enrich.providers.gemini import GeminiProvider

BOM = json.dumps({"compat_score": 80, "compat_reasoning": "ok", "verdict": "avaliar"})


class _FakeClient:
    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.chamadas = 0
        self.models = self

    def generate_content(self, **kwargs):
        self.chamadas += 1
        r = self._respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return type("Resp", (), {"text": r})()


def test_json_valido_de_primeira():
    p = GeminiProvider(cliente=_FakeClient([BOM]))
    d = p.analisar("prompt")
    assert d["compat_score"] == 80
    assert p._cliente.chamadas == 1


def test_json_sujo_faz_retry_e_recupera():
    p = GeminiProvider(cliente=_FakeClient(["não é json", "```json\n" + BOM + "\n```"]))
    d = p.analisar("prompt")
    assert d["compat_score"] == 80
    assert p._cliente.chamadas == 2


def test_json_ruim_nas_duas_levanta_invalida():
    p = GeminiProvider(cliente=_FakeClient(["lixo", "mais lixo"]))
    with pytest.raises(LLMRespostaInvalida):
        p.analisar("prompt")


def test_erro_de_rede_levanta_indisponivel():
    p = GeminiProvider(cliente=_FakeClient([ConnectionError("timeout")]))
    with pytest.raises(LLMIndisponivel):
        p.analisar("prompt")
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_enrich_provider_gemini.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# enrich/providers/base.py
from abc import ABC, abstractmethod


class LLMIndisponivel(Exception):
    """Falha dura: rede, autenticação, rate-limit. Ciclo deve parar de chamar o LLM."""


class LLMRespostaInvalida(Exception):
    """Modelo respondeu, mas não foi possível extrair JSON válido após retry."""


class LLMProvider(ABC):
    @abstractmethod
    def analisar(self, prompt: str) -> dict:
        ...
```

```python
# enrich/providers/gemini.py
import json
import re

from logger import get_logger
from .base import LLMProvider, LLMIndisponivel, LLMRespostaInvalida

logger = get_logger()

_MODELO = "gemini-2.0-flash"


def _extrair_json(texto: str) -> dict:
    texto = texto.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.DOTALL)
    candidato = m.group(1) if m else texto
    inicio, fim = candidato.find("{"), candidato.rfind("}")
    if inicio == -1 or fim == -1:
        raise ValueError("sem objeto JSON no texto")
    return json.loads(candidato[inicio:fim + 1])


class GeminiProvider(LLMProvider):
    def __init__(self, cliente=None, api_key: str | None = None):
        if cliente is not None:
            self._cliente = cliente
            return
        from config import GEMINI_API_KEY
        from google import genai  # import tardio: só quem usa Gemini precisa da lib
        chave = api_key or GEMINI_API_KEY
        if not chave:
            raise LLMIndisponivel("GEMINI_API_KEY não configurada")
        self._cliente = genai.Client(api_key=chave)

    def analisar(self, prompt: str) -> dict:
        ultimo_texto = ""
        for tentativa in (1, 2):
            try:
                resp = self._cliente.models.generate_content(
                    model=_MODELO,
                    contents=prompt if tentativa == 1 else prompt + "\n\nATENÇÃO: responda SÓ o JSON, nada mais.",
                    config={"response_mime_type": "application/json", "temperature": 0.2},
                )
            except Exception as e:  # rede, auth, rate-limit, quota
                raise LLMIndisponivel(f"Gemini: {type(e).__name__}: {e}") from e
            ultimo_texto = getattr(resp, "text", "") or ""
            try:
                return _extrair_json(ultimo_texto)
            except (ValueError, json.JSONDecodeError):
                logger.warning(f"[gemini] resposta não-JSON (tentativa {tentativa}): {ultimo_texto[:120]!r}")
        raise LLMRespostaInvalida(f"Gemini não devolveu JSON válido em 2 tentativas: {ultimo_texto[:200]!r}")
```

```python
# enrich/providers/__init__.py
from .base import LLMProvider, LLMIndisponivel, LLMRespostaInvalida


def obter_provider(nome: str | None = None) -> LLMProvider:
    from config import LLM_PROVIDER
    nome = (nome or LLM_PROVIDER).lower()
    if nome == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider()
    raise LLMIndisponivel(f"LLM_PROVIDER desconhecido: {nome!r}")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_enrich_provider_gemini.py -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Commit**

```bash
git add enrich/providers/ tests/test_enrich_provider_gemini.py
git commit -m "feat(enrich): interface LLMProvider + implementação Gemini Flash"
```

---

## Task 6: `enrich/fetch_detail.py` — descrição completa da vaga

**Files:**
- Create: `enrich/fetch_detail.py`
- Test: `tests/test_enrich_fetch_detail.py`

**Interfaces:**
- Consumes: `job.Job` (`link`, `site`); opcional `job.descricao` já preenchida (Greenhouse)
- Produces: `enrich.fetch_detail.buscar_descricao(job) -> tuple[str, bool]` — `(texto, completo)`. `completo=False` quando caiu no fallback (texto do card / falha).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrich_fetch_detail.py
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
    monkeypatch.setattr(fd, "_get_html", lambda url: "<html><body><main>Requisitos: Python, SQL.</main></body></html>")
    texto, completo = buscar_descricao(_job())
    assert "Requisitos: Python, SQL." in texto
    assert completo is True


def test_falha_cai_no_fallback_card(monkeypatch):
    import enrich.fetch_detail as fd
    monkeypatch.setattr(fd, "_get_html", lambda url: (_ for _ in ()).throw(ConnectionError()))
    j = _job()
    j.descricao = ""
    texto, completo = buscar_descricao(j)
    assert j.titulo in texto and j.empresa in texto
    assert completo is False
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_enrich_fetch_detail.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# enrich/fetch_detail.py
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
        if len(texto) >= 200:
            return texto, True
        logger.warning(f"[fetch_detail] descrição curta demais ({len(texto)}) em {job.link} — fallback")
    except Exception as e:
        logger.warning(f"[fetch_detail] falha em {job.link}: {type(e).__name__}: {e} — fallback")
    return _fallback_card(job), False
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_enrich_fetch_detail.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add enrich/fetch_detail.py tests/test_enrich_fetch_detail.py
git commit -m "feat(enrich): buscar descrição completa da vaga (com fallback pro card)"
```

---

## Task 7: `job.py` — campo `descricao` e `analise` no `Job`

**Files:**
- Modify: `job.py` (dataclass `Job`, ~linha 803–807)
- Test: `tests/test_job_campos_enrich.py`

**Interfaces:**
- Produces: `Job.descricao: str = ""` e `Job.analise: "Analysis | None" = None` (anotação string — sem import de `enrich` em `job.py`, evita ciclo)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_job_campos_enrich.py
from job import Job


def test_job_tem_descricao_e_analise_default():
    j = Job(titulo="X", empresa="Y", local="Z", link="http://x/1", site="S")
    assert j.descricao == ""
    assert j.analise is None
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_job_campos_enrich.py -v`
Expected: FAIL — `AttributeError: 'Job' object has no attribute 'descricao'`

- [ ] **Step 3: Implement**

```python
# job.py — dentro do @dataclass class Job, junto de relevancia/motivo (~linha 803)

    # Descrição completa da vaga, preenchida por scrapers que já trazem
    # (Greenhouse) ou pelo enrich/fetch_detail.py no estágio 2. "" quando
    # não buscada ainda.
    descricao: str = ""
    # Resultado da análise LLM (enrich/). None = não analisada ou análise
    # falhou (nesse caso o routing cai no fallback heurístico por relevancia).
    # Anotação como string pra não importar enrich aqui (evita ciclo).
    analise: "object | None" = None
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_job_campos_enrich.py -v && pytest tests/test_filtro.py -q`
Expected: PASS; nenhuma regressão em test_filtro

- [ ] **Step 5: Commit**

```bash
git add job.py tests/test_job_campos_enrich.py
git commit -m "feat: campos descricao e analise no Job"
```

---

## Task 8: `enrich/analyze.py` — orquestrador do estágio 2

**Files:**
- Create: `enrich/analyze.py`
- Test: `tests/test_enrich_analyze.py`

**Interfaces:**
- Consumes: `enrich.fetch_detail.buscar_descricao`, `enrich.prompt.montar_prompt`, `enrich.models.Analysis`, `enrich.providers.obter_provider`, `enrich.baseline.carregar_cv`
- Produces:
  - `enrich.analyze.analisar_vaga(job, cv_text, provider, hint="dev") -> Analysis | None` — pipeline de uma vaga; `None` em qualquer falha (logada).
  - `enrich.analyze.analisar_vagas(jobs: list, hint="dev") -> None` — monta provider de `config`, itera, seta `job.analise` in-place; após `config.ENRICH_MAX_FALHAS_LLM` `LLMIndisponivel` seguidas para de chamar (resto fica `analise=None`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrich_analyze.py
import pytest
from enrich.analyze import analisar_vaga, analisar_vagas
from enrich.providers.base import LLMIndisponivel
from job import Job

BOM = {"compat_score": 90, "compat_reasoning": "forte", "verdict": "candidatar",
       "salary_estimate": {"min": 4000, "max": 6000}}


def _job(t="DevOps Júnior"):
    return Job(titulo=t, empresa="ACME", local="Remoto", link="http://x/1", site="S", descricao="Terraform, AWS.")


class _Prov:
    def __init__(self, resultado):
        self.resultado = resultado
        self.chamadas = 0

    def analisar(self, prompt):
        self.chamadas += 1
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self.resultado


def test_sucesso_devolve_analysis():
    a = analisar_vaga(_job(), "CV texto", _Prov(BOM))
    assert a.compat_score == 90
    assert a.verdict == "candidatar"


def test_provider_falha_devolve_none():
    assert analisar_vaga(_job(), "CV", _Prov(LLMIndisponivel("rate limit"))) is None


def test_json_incompleto_devolve_none():
    assert analisar_vaga(_job(), "CV", _Prov({"compat_score": 50})) is None  # sem verdict


def test_analisar_vagas_para_apos_n_falhas(monkeypatch):
    import enrich.analyze as az
    prov = _Prov(LLMIndisponivel("quota"))
    monkeypatch.setattr(az, "obter_provider", lambda: prov)
    monkeypatch.setattr(az, "carregar_cv", lambda: "CV")
    monkeypatch.setattr("config.ENRICH_MAX_FALHAS_LLM", 2, raising=False)
    jobs = [_job(f"vaga {i}") for i in range(5)]
    analisar_vagas(jobs)
    assert prov.chamadas == 2  # parou após 2 falhas
    assert all(j.analise is None for j in jobs)


def test_analisar_vagas_seta_in_place(monkeypatch):
    import enrich.analyze as az
    monkeypatch.setattr(az, "obter_provider", lambda: _Prov(BOM))
    monkeypatch.setattr(az, "carregar_cv", lambda: "CV")
    jobs = [_job()]
    analisar_vagas(jobs)
    assert jobs[0].analise.compat_score == 90
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_enrich_analyze.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# enrich/analyze.py
from logger import get_logger
from .baseline import carregar_cv
from .fetch_detail import buscar_descricao
from .models import Analysis
from .prompt import montar_prompt
from .providers import obter_provider
from .providers.base import LLMIndisponivel, LLMRespostaInvalida

logger = get_logger()


def analisar_vaga(job, cv_text: str, provider, hint: str = "dev") -> Analysis | None:
    descricao, completo = buscar_descricao(job)
    job.descricao = descricao
    prompt = montar_prompt(job, descricao, cv_text, hint)
    try:
        cru = provider.analisar(prompt)
    except LLMRespostaInvalida as e:
        logger.warning(f"[analyze] resposta inválida pra '{job.titulo}': {e}")
        return None
    # LLMIndisponivel NÃO é capturado aqui — sobe pra analisar_vagas decidir parar.
    cru["descricao_parcial"] = not completo
    try:
        return Analysis.from_dict(cru)
    except ValueError as e:
        logger.warning(f"[analyze] JSON incompleto pra '{job.titulo}': {e}")
        return None


def analisar_vagas(jobs: list, hint: str = "dev") -> None:
    if not jobs:
        return
    import config
    try:
        provider = obter_provider()
    except LLMIndisponivel as e:
        logger.warning(f"[analyze] provider indisponível ({e}) — ciclo sem análise LLM, fallback heurístico.")
        return
    cv_text = carregar_cv()
    falhas_seguidas = 0
    analisadas = 0
    for job in jobs:
        try:
            job.analise = analisar_vaga(job, cv_text, provider, hint)
            falhas_seguidas = 0
            if job.analise:
                analisadas += 1
        except LLMIndisponivel as e:
            falhas_seguidas += 1
            logger.warning(f"[analyze] LLM indisponível ({falhas_seguidas}/{config.ENRICH_MAX_FALHAS_LLM}): {e}")
            if falhas_seguidas >= config.ENRICH_MAX_FALHAS_LLM:
                logger.warning("[analyze] limite de falhas atingido — resto do ciclo sem LLM.")
                return
    logger.info(f"[analyze] {analisadas}/{len(jobs)} vaga(s) analisadas pelo LLM.")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_enrich_analyze.py -v`
Expected: PASS (5 testes)

- [ ] **Step 5: Commit**

```bash
git add enrich/analyze.py tests/test_enrich_analyze.py
git commit -m "feat(enrich): orquestrador analisar_vaga/analisar_vagas + guard de falhas"
```

---

## Task 9: `database/database.py` — persistir a análise

**Files:**
- Modify: `database/database.py` (novo `_garantir_colunas_analise`, chamar em `iniciar_db`; `salvar_vaga`; `obter_vagas_pendentes_digest`)
- Test: `tests/test_database_analise.py`

**Interfaces:**
- Consumes: `enrich.models.Analysis` (via `.to_json()` e `.compat_score`)
- Produces:
  - `salvar_vaga(job, perfil_chave="", digest_pendente=False, exploratoria=False, analise=None)` — grava `compat_score` e `analise_json` quando `analise` não é None
  - `obter_vagas_pendentes_digest(perfil_chave)` passa a retornar tuplas `(titulo, empresa, link, relevancia, exploratoria, compat_score, analise_json)` ordenadas por `COALESCE(compat_score, relevancia*10) DESC`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_database_analise.py
import json
import database.database as db
from job import Job
from enrich.models import Analysis


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.iniciar_db()


def _analise(score):
    return Analysis.from_dict({"compat_score": score, "compat_reasoning": "x", "verdict": "avaliar"})


def test_migracao_idempotente(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    db.iniciar_db()  # roda de novo, não pode quebrar
    with db._conectar() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(vagas_vistas)")}
    assert {"compat_score", "analise_json"} <= cols


def test_salvar_e_ler_com_analise(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    j = Job(titulo="DevOps Jr", empresa="ACME", local="Remoto", link="http://x/1", site="S")
    j.relevancia = 6
    db.salvar_vaga(j, perfil_chave="brasil", digest_pendente=True, analise=_analise(92))
    linhas = db.obter_vagas_pendentes_digest("brasil")
    assert len(linhas) == 1
    titulo, empresa, link, rel, expl, compat, aj = linhas[0]
    assert compat == 92
    assert json.loads(aj)["compat_score"] == 92


def test_digest_ordena_por_compat_depois_relevancia(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    a = Job(titulo="A", empresa="E", local="R", link="http://x/a", site="S"); a.relevancia = 9
    b = Job(titulo="B", empresa="E", local="R", link="http://x/b", site="S"); b.relevancia = 3
    db.salvar_vaga(a, perfil_chave="brasil", digest_pendente=True)  # sem análise -> 9*10=90
    db.salvar_vaga(b, perfil_chave="brasil", digest_pendente=True, analise=_analise(95))
    linhas = db.obter_vagas_pendentes_digest("brasil")
    assert linhas[0][0] == "B"  # compat 95 > 90
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_database_analise.py -v`
Expected: FAIL — coluna `compat_score` não existe / `salvar_vaga` não aceita `analise`

- [ ] **Step 3: Implement**

```python
# database/database.py

def _garantir_colunas_analise(conn):
    colunas = {row[1] for row in conn.execute("PRAGMA table_info(vagas_vistas)")}
    if "compat_score" not in colunas:
        conn.execute("ALTER TABLE vagas_vistas ADD COLUMN compat_score INTEGER")
    if "analise_json" not in colunas:
        conn.execute("ALTER TABLE vagas_vistas ADD COLUMN analise_json TEXT")


# em iniciar_db(), junto das outras chamadas _garantir_*:
        _garantir_colunas_analise(conn)


# salvar_vaga — nova assinatura e INSERT:
def salvar_vaga(job, perfil_chave: str = "", digest_pendente: bool = False,
                exploratoria: bool = False, analise=None):
    compat = analise.compat_score if analise is not None else None
    analise_json = analise.to_json() if analise is not None else None
    with _conectar() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO vagas_vistas
               (id, titulo, empresa, local, link, site, chave_secundaria, publicado_em,
                modalidade, relevancia, perfil, digest_pendente, exploratoria, situacao,
                compat_score, analise_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (job.id, job.titulo, job.empresa, job.local, job.link, job.site,
             job.chave_secundaria, job.publicado_em, job.modalidade, job.relevancia,
             perfil_chave, int(digest_pendente), int(exploratoria), "nova",
             compat, analise_json),
        )


# obter_vagas_pendentes_digest — novo SELECT/ORDER:
        cur = conn.execute(
            """SELECT titulo, empresa, link, relevancia, exploratoria, compat_score, analise_json
               FROM vagas_vistas
               WHERE perfil = ? AND digest_pendente = 1
               ORDER BY COALESCE(compat_score, relevancia * 10) DESC, encontrada_em ASC""",
            (perfil_chave,),
        )
```

> Ajuste o INSERT ao formato exato já usado no arquivo (a lista de colunas atual está em `database.py:249-258`). Só acrescente `compat_score, analise_json` ao final das colunas e `compat, analise_json` ao final dos valores.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_database_analise.py tests/ -q`
Expected: PASS; suíte inteira verde (o 6º/7º campo novo em `obter_vagas_pendentes_digest` pode quebrar `notifier/telegram.py:montar_digest` — corrigido na Task 11; se rodar a suíte toda agora e `test_telegram` falhar por unpack, é esperado até a Task 11)

- [ ] **Step 5: Commit**

```bash
git add database/database.py tests/test_database_analise.py
git commit -m "feat(db): colunas compat_score/analise_json + ordenação do digest por compat"
```

---

## Task 10: `main.py` — ligar o estágio 2 no ciclo

**Files:**
- Modify: `main.py` (`ciclo_de_busca` — o loop `for vaga in vagas_filtradas`)
- Modify: `config.py` (nada novo; `LIMIAR_COMPAT_IMEDIATO` já veio na Task 1)
- Test: `tests/test_main_routing.py`

**Interfaces:**
- Consumes: `enrich.analyze.analisar_vagas`, `config.LIMIAR_COMPAT_IMEDIATO`
- Produces: helper `main._deve_notificar_imediato(vaga) -> bool` — `True` se (análise presente e `compat_score >= LIMIAR_COMPAT_IMEDIATO`) OU (sem análise e `relevancia >= LIMIAR_DIGEST_IMEDIATO`); sempre `False` se `vaga.publicacao_antiga`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main_routing.py
import main
from job import Job
from enrich.models import Analysis


def _job(rel=0):
    j = Job(titulo="X", empresa="Y", local="Remoto", link="http://x/1", site="S")
    j.relevancia = rel
    return j


def _an(score):
    return Analysis.from_dict({"compat_score": score, "compat_reasoning": "x", "verdict": "avaliar"})


def test_analise_acima_do_limiar_notifica():
    j = _job(); j.analise = _an(90)
    assert main._deve_notificar_imediato(j) is True


def test_analise_abaixo_vai_pro_digest():
    j = _job(rel=9); j.analise = _an(50)  # relevancia alta não salva: com análise, manda a análise
    assert main._deve_notificar_imediato(j) is False


def test_sem_analise_usa_relevancia():
    assert main._deve_notificar_imediato(_job(rel=8)) is True
    assert main._deve_notificar_imediato(_job(rel=4)) is False


def test_vaga_antiga_nunca_imediata(monkeypatch):
    j = _job(); j.analise = _an(99)
    monkeypatch.setattr(type(j), "publicacao_antiga", property(lambda self: True))
    assert main._deve_notificar_imediato(j) is False
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_main_routing.py -v`
Expected: FAIL — `AttributeError: module 'main' has no attribute '_deve_notificar_imediato'`

- [ ] **Step 3: Implement**

```python
# main.py — novo import
from config import (DIGEST_HORA_UTC, INTERVALO_MINUTOS, LIMIAR_DIGEST_IMEDIATO,
                    LIMIAR_COMPAT_IMEDIATO)
from enrich.analyze import analisar_vagas

# novo helper (nível de módulo)
def _deve_notificar_imediato(vaga) -> bool:
    if vaga.publicacao_antiga:
        return False
    if vaga.analise is not None:
        return vaga.analise.compat_score >= LIMIAR_COMPAT_IMEDIATO
    return vaga.relevancia >= LIMIAR_DIGEST_IMEDIATO
```

```python
# main.py — dentro de ciclo_de_busca, SUBSTITUIR o trecho:
#     novas_da_fonte = 0
#     for vaga in vagas_filtradas:
#         if ja_vista(vaga):
#             continue
#         if vaga.relevancia >= LIMIAR_DIGEST_IMEDIATO and not vaga.publicacao_antiga:
#             ... (notificar) ...
#         else:
#             ... (digest) ...
# POR:

            vagas_novas = [v for v in vagas_filtradas if not ja_vista(v)]
            # Estágio 2: análise profunda só nas novas que passaram o filtro barato.
            analisar_vagas(vagas_novas, hint="dev")

            novas_da_fonte = 0
            for vaga in vagas_novas:
                if _deve_notificar_imediato(vaga):
                    if not notificar_vaga(vaga):
                        logger.warning(
                            f"[{perfil.nome}] Falha ao notificar '{vaga.titulo}' - não marcada "
                            "como vista, tenta de novo no próximo ciclo."
                        )
                        continue
                    salvar_vaga(vaga, perfil_chave=perfil.chave, analise=vaga.analise)
                    logger.info(f"[{perfil.nome}] Nova vaga: {vaga.titulo} - {vaga.empresa}")
                else:
                    salvar_vaga(vaga, perfil_chave=perfil.chave, digest_pendente=True,
                                analise=vaga.analise)
                    if vaga.analise is not None:
                        motivo = f"compat {vaga.analise.compat_score}%"
                    elif vaga.publicacao_antiga:
                        motivo = "vaga antiga"
                    else:
                        motivo = f"relevância {vaga.relevancia}/10"
                    logger.info(
                        f"[{perfil.nome}] Nova vaga (digest, {motivo}): {vaga.titulo} - {vaga.empresa}"
                    )
                total_novas += 1
                novas_da_fonte += 1
```

> O bloco `vagas_secundarias` (eixo Ibéria) fica como está — hoje está desligado (`ATIVAR_EIXO_IBERICO_BR = False`), e análise LLM no eixo exploratório entra só se/quando ele voltar. Se o `for vaga in vagas_secundarias` referencia `LIMIAR_DIGEST_IMEDIATO`, mantenha; não passe `analise=` lá.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_main_routing.py -v && pytest tests/ -q`
Expected: `test_main_routing` PASS; suíte verde exceto `test_telegram` (Task 11)

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main_routing.py
git commit -m "feat: liga o estágio 2 (análise LLM) no ciclo; routing por compat_score com fallback"
```

---

## Task 11: `notifier/telegram.py` — card e digest com a análise

**Files:**
- Modify: `notifier/telegram.py` (`notificar_vaga`, `montar_digest`)
- Test: `tests/test_telegram_analise.py`, ajustar `tests/test_telegram.py` (unpack de 7 campos)

**Interfaces:**
- Consumes: `job.analise` (`enrich.models.Analysis`); tuplas de `obter_vagas_pendentes_digest` agora com 7 campos
- Produces: `notifier.telegram._bloco_analise(analise) -> str` (string HTML pronta pra concatenar; "" se `analise` None)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_telegram_analise.py
from notifier.telegram import _bloco_analise, montar_digest
from enrich.models import Analysis


def _an(**kw):
    base = {"compat_score": 88, "compat_reasoning": "Stack bate.", "verdict": "candidatar",
            "verdict_reason": "sem bloqueio",
            "salary_estimate": {"min": 3500, "max": 5000, "confianca": "media"},
            "gaps": [{"requisito": "Kubernetes", "severidade": "importante"},
                     {"requisito": "Inglês fluente", "severidade": "bloqueante"}]}
    base.update(kw)
    return Analysis.from_dict(base)


def test_bloco_analise_tem_score_salario_e_gaps():
    txt = _bloco_analise(_an())
    assert "88%" in txt
    assert "3500" in txt and "5000" in txt
    assert "Kubernetes" in txt
    assert "Inglês fluente" in txt  # bloqueante aparece
    assert "candidatar" in txt.lower()


def test_bloco_analise_none_vira_vazio():
    assert _bloco_analise(None) == ""


def test_digest_mostra_compat_quando_tem(monkeypatch):
    # tupla: (titulo, empresa, link, relevancia, exploratoria, compat_score, analise_json)
    linhas = [("DevOps Jr", "ACME", "http://x/1", 5, 0, 91, _an(compat_score=91).to_json())]
    msgs = montar_digest(linhas, "Brasil")
    assert any("91%" in m for m in msgs)
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_telegram_analise.py -v`
Expected: FAIL — `_bloco_analise` não existe; `montar_digest` quebra no unpack

- [ ] **Step 3: Implement**

```python
# notifier/telegram.py

def _bloco_analise(analise) -> str:
    if analise is None:
        return ""
    s = analise.salary_estimate
    linhas = [f"\n📊 <b>Compatibilidade: {analise.compat_score}%</b> — {analise.verdict}"]
    if analise.compat_reasoning:
        linhas.append(f"<i>{analise.compat_reasoning}</i>")
    if s.min and s.max:
        linhas.append(f"💰 R$ {s.min}–{s.max}/mês (confiança {s.confianca})")
    elif s.base:
        linhas.append(f"💰 salário n/d — {s.base}")
    bloqueantes = [g for g in analise.gaps if g.severidade == "bloqueante"]
    outros = [g for g in analise.gaps if g.severidade != "bloqueante"]
    if bloqueantes:
        linhas.append("🚫 <b>Bloqueante:</b> " + "; ".join(g.requisito for g in bloqueantes))
    if outros:
        linhas.append("⚠️ Lacunas: " + "; ".join(g.requisito for g in outros[:4]))
    if analise.strengths:
        linhas.append("✅ " + "; ".join(analise.strengths[:3]))
    return "\n".join(linhas) + "\n"


# notificar_vaga(job): concatenar `_bloco_analise(job.analise)` no corpo da mensagem,
# antes do teclado de feedback.

# montar_digest(vagas, rotulo_perfil): o unpack de cada tupla passa a ter 7 campos.
# Para cada linha, se compat_score não for None, mostrar "<compat>%" no lugar/junto
# da linha de relevância. Ex.:
#     titulo, empresa, link, relevancia, exploratoria, compat_score, analise_json = vaga
#     marcador = f"{compat_score}%" if compat_score is not None else f"rel {relevancia}/10"
```

- [ ] **Step 4: Fix `tests/test_telegram.py`**

Atualizar as tuplas de teste de `montar_digest`/`obter_vagas_pendentes_digest` de 5 para 7 campos (`+ compat_score, analise_json` — pode passar `None, None`).

- [ ] **Step 5: Run tests**

Run: `pytest tests/ -q`
Expected: PASS — suíte inteira verde

- [ ] **Step 6: Commit**

```bash
git add notifier/telegram.py tests/test_telegram_analise.py tests/test_telegram.py
git commit -m "feat(telegram): card e digest mostram compat%, salário e lacunas"
```

---

## Task 12: `scrapers/greenhouse.py` — nova fonte

**Files:**
- Create: `scrapers/greenhouse.py`
- Modify: `perfis.py` (`_SCRAPERS_BR` — adicionar `GreenhouseScraper` como `FREQUENCIA_BAIXA`)
- Modify: `config.py` (`GREENHOUSE_BOARDS` já veio na Task 1; adicionar 5–10 slugs iniciais como default se `.env` não define — ver step 3)
- Test: `tests/test_greenhouse.py`

**Interfaces:**
- Consumes: `job.Job`, `config.GREENHOUSE_BOARDS`
- Produces: `scrapers.greenhouse.GreenhouseScraper(termos_busca: list[str])` com `buscar_vagas() -> list[Job]` (padrão `BaseScraper`). Cada Job vem com `descricao` já preenchida.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_greenhouse.py
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
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_greenhouse.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# scrapers/greenhouse.py
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
    lista GREENHOUSE_BOARDS (slugs de empresa). API traz a descrição inteira
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
```

```python
# perfis.py — em _SCRAPERS_BR, adicionar:
    DefinicaoScraper(GreenhouseScraper, FREQUENCIA_BAIXA),   # boards por empresa, descrição completa
# e o import no topo:
from scrapers.greenhouse import GreenhouseScraper
```

```python
# config.py — dar um default útil pro GREENHOUSE_BOARDS (empresas de tech BR
# conhecidas por publicar júnior no Greenhouse — validar cada slug abrindo
# boards.greenhouse.io/<slug>):
_GREENHOUSE_DEFAULT = "nubank,hotmart,loft,quintoandar,mercadolibre"
GREENHOUSE_BOARDS = [
    b.strip() for b in os.getenv("GREENHOUSE_BOARDS", _GREENHOUSE_DEFAULT).split(",") if b.strip()
]
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_greenhouse.py -v && python -c "import perfis"`
Expected: PASS; `perfis` importa

- [ ] **Step 5: Verificação ao vivo (manual, não-CI)**

Run: `python -c "from scrapers.greenhouse import GreenhouseScraper; [print(v.titulo, v.link) for v in GreenhouseScraper(['developer','devops','junior','júnior','estagi']).buscar_vagas()]"`
Expected: lista real de vagas dos boards default (ou lista vazia + warnings se os slugs estiverem errados — ajustar `_GREENHOUSE_DEFAULT`)

- [ ] **Step 6: Commit**

```bash
git add scrapers/greenhouse.py perfis.py config.py tests/test_greenhouse.py
git commit -m "feat(scraper): Greenhouse (boards por empresa, descrição completa via API)"
```

---

## Task 13: vocabulário cloud/devops no `config.py`

**Files:**
- Modify: `config.py` (`KEYWORDS_CARGO_FORTE`, `KEYWORDS_CARGO_AMBIGUO`, `QUALIFICADORES_CARGO`, `FERRAMENTAS_TITULO`, `TERMOS_CARGO`)
- Modify: `tests/test_filtro.py` (casos novos)
- Test: `tests/test_filtro.py`

**Interfaces:**
- Consumes: listas existentes em `config.py`
- Produces: nada novo — estende dados existentes

- [ ] **Step 1: Write the failing test**

```python
# tests/test_filtro.py — adicionar ao final da lista CASOS_ESCOPO ou num bloco novo
from job import Job
from perfis import PERFIL_BR


def _vaga(titulo, local="Recife, PE", modalidade="Remoto"):
    return Job(titulo=titulo, empresa="X", local=local, link=f"http://x/{titulo}", site="S", modalidade=modalidade)


def test_devops_junior_remoto_passa():
    assert _vaga("DevOps Júnior").combina_com(PERFIL_BR.regras) is True


def test_cloud_engineer_junior_passa():
    assert _vaga("Cloud Engineer Júnior (AWS)").combina_com(PERFIL_BR.regras) is True


def test_sre_senior_reprova():
    assert _vaga("Site Reliability Engineer Sênior").combina_com(PERFIL_BR.regras) is False


def test_analista_de_redes_fora_de_escopo():
    assert _vaga("Analista de Redes e Infraestrutura").combina_com(PERFIL_BR.regras) is False


def test_devops_sem_qualificador_junior_nao_passa():
    # "DevOps" ambíguo sozinho, sem júnior/estágio no título -> não passa (mesma regra do dev)
    assert _vaga("Engenheiro DevOps").combina_com(PERFIL_BR.regras) is False
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_filtro.py -k "devops or cloud or sre or redes" -v`
Expected: FAIL — `DevOps Júnior` etc. não batem nenhuma keyword

- [ ] **Step 3: Implement**

```python
# config.py — acrescentar às listas existentes (NÃO substituir):

KEYWORDS_CARGO_FORTE += [
    "DevOps Júnior", "DevOps Jr", "Júnior DevOps",
    "Cloud Engineer Júnior", "Engenheiro de Cloud Júnior",
    "Platform Engineer Júnior", "Engenheiro de Plataforma Júnior",
    "SRE Júnior", "Site Reliability Engineer Júnior",
    "DevSecOps Júnior", "Estágio DevOps", "Estágio em Cloud",
]

KEYWORDS_CARGO_AMBIGUO += [
    "DevOps", "Cloud Engineer", "Engenheiro de Cloud", "Platform Engineer",
    "Engenheiro de Plataforma", "SRE", "Site Reliability", "DevSecOps",
]

QUALIFICADORES_CARGO += ["devops", "cloud", "sre", "plataforma", "platform", "devsecops"]

FERRAMENTAS_TITULO += ["kubernetes", "k8s", "terraform", "docker", "aws", "gcp", "azure", "ci/cd"]

# TERMOS_CARGO (o que é pesquisado nos sites) — acrescentar:
TERMOS_CARGO += [
    "devops júnior", "cloud engineer júnior", "platform engineer júnior",
    "sre júnior", "estágio devops", "estágio cloud", "devsecops júnior",
]
```

> Verifique os nomes exatos das listas em `config.py` antes (linhas ~59–144). Se `TERMOS_CARGO`/`TERMOS_FERRAMENTA` tiverem outro nome, use o correto. `TERMOS_BUSCA = TERMOS_CARGO + TERMOS_FERRAMENTA` (linha 144) pega os novos automaticamente.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_filtro.py -q`
Expected: PASS — casos novos verdes, nenhuma regressão nos antigos

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_filtro.py
git commit -m "feat: vocabulário da trilha cloud/devops (júnior) no filtro"
```

---

## Task 14: `deploy/` — launchd no Mac + README de migração

**Files:**
- Create: `deploy/com.rodolfo.jobradar.plist`
- Create: `deploy/jobradar.service`
- Create: `deploy/README.md`
- Modify: `README.md` (raiz — apontar pro deploy/)

**Interfaces:** nenhuma (arquivos de infra)

- [ ] **Step 1: Criar o plist do launchd**

```xml
<!-- deploy/com.rodolfo.jobradar.plist
     Instalar: copiar pra ~/Library/LaunchAgents/, ajustar os caminhos,
     `launchctl load ~/Library/LaunchAgents/com.rodolfo.jobradar.plist` -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.rodolfo.jobradar</string>
  <key>WorkingDirectory</key><string>/Users/rodolfoferraz/git/job-radar</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/rodolfoferraz/git/job-radar/.venv/bin/python</string>
    <string>main.py</string>
    <string>--perfil</string><string>brasil</string>
    <string>--once</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>13</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>19</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>22</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key><string>/tmp/jobradar.out.log</string>
  <key>StandardErrorPath</key><string>/tmp/jobradar.err.log</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
```

- [ ] **Step 2: Criar o service do systemd (VM, pronto e parado)**

```ini
# deploy/jobradar.service — VM. Usar com um timer (jobradar.timer) OU cron.
# Não habilitar até a migração (ver README).
[Unit]
Description=JobRadar - um ciclo de busca
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/job-radar
EnvironmentFile=/opt/job-radar/.env
ExecStart=/opt/job-radar/.venv/bin/python main.py --perfil brasil --once
```

- [ ] **Step 3: Escrever o README de deploy**

```markdown
# Deploy

## Mac (agora) — launchd

1. `cd ~/git/job-radar && python -m venv .venv && .venv/bin/pip install -r requirements.txt`
2. `.venv/bin/python -m playwright install chromium`
3. `cp .env.example .env` e preencher (`GEMINI_API_KEY`, `TELEGRAM_*`, `CV_PATH`).
4. `cp deploy/com.rodolfo.jobradar.plist ~/Library/LaunchAgents/`
   — ajustar `WorkingDirectory` e o path do python se o checkout não for `~/git/job-radar`.
5. `launchctl load ~/Library/LaunchAgents/com.rodolfo.jobradar.plist`
6. Testar 1 ciclo na mão: `.venv/bin/python main.py --perfil brasil --once`
7. Logs: `/tmp/jobradar.out.log` e `/tmp/jobradar.err.log`.

Desligar: `launchctl unload ~/Library/LaunchAgents/com.rodolfo.jobradar.plist`

**Não reinicie o processo no meio de um ciclo** (mesma disciplina do workout-generator):
o ciclo é curto (~2–5 min), espere terminar. Matar no meio pode deixar o SQLite
num estado meia-boca (raro, mas evitável).

## VM (depois) — systemd

1. `git clone` em `/opt/job-radar`, `python -m venv .venv`, `pip install -r requirements.txt`, `playwright install chromium`.
2. Criar `/opt/job-radar/.env` com o mesmo conteúdo do Mac.
3. `cp deploy/jobradar.service /etc/systemd/system/`
4. Criar `/etc/systemd/system/jobradar.timer` (a cada 3h, 07–22) OU um cron equivalente.
5. `systemctl daemon-reload && systemctl enable --now jobradar.timer`
6. Migrar o histórico: `scp` do `data/jobs.db` do Mac pra VM ANTES do primeiro run
   (senão o `BancoVazioSuspeito` aborta, ou notifica tudo de novo).

## SQLite -> Postgres (só se precisar)

`database/database.py` é o único arquivo que toca o banco. Trocar as funções
`_conectar`/`iniciar_db`/`salvar_vaga`/etc. pra um driver Postgres, mantendo as
mesmas assinaturas. Nenhum outro módulo muda.
```

- [ ] **Step 4: Verificação**

Run: `plutil -lint deploy/com.rodolfo.jobradar.plist`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add deploy/ README.md
git commit -m "feat(deploy): launchd (Mac) + systemd (VM, parado) + README de migração"
```

---

## Self-Review

**1. Spec coverage:**

| Requisito do spec | Task |
|---|---|
| Roda local no Mac via launchd | 14 |
| Perfil dev expandido (cloud/devops) | 13 |
| Funil 2 estágios (heurística → LLM) | 8, 10 |
| Estimativa de salário | 2, 4 (schema+prompt), aparece em 11 |
| Análise de lacunas | 2, 4, 11 |
| Alerta imediato acima de limiar (default 85) | 1, 10 |
| Greenhouse | 12 |
| Buscar detalhe só nas sobreviventes | 6, 8, 10 |
| LinkedIn só guest (sem mudança) | — (nada toca linkedin.py) |
| `.env` / secrets fora do git | 1, 14 |
| Fallback heurístico quando LLM falha | 5 (exceptions), 8 (guard), 10 (`_deve_notificar_imediato`) |
| Provider agnóstico (Anthropic depois) | 5 (`obter_provider`, ABC) |
| Migração de schema incremental | 9 |
| CV V3 como baseline | 3 |
| Testes dos módulos novos, sem chamar LLM no CI | todas as tasks têm testes com mock |
| Fase 2 fora de escopo (FastAPI/Postgres/orquestrador/outros agentes/Workday/dashboard) | não há task pra nenhum — correto |

Sem lacunas.

**2. Placeholder scan:** nenhum "TBD"/"implementar depois"/"tratar edge cases" sem código. Os 3 pontos com `>` (nota) apontam pra ajuste de detalhe verificável no arquivo real (formato exato do INSERT, nomes exatos das listas), não pra lógica omitida.

**3. Type consistency:**
- `Analysis.compat_score: int` — usado como int em `_deve_notificar_imediato` (Task 10), `salvar_vaga` (Task 9), `_bloco_analise` (Task 11). ✓
- `Analysis.from_dict` / `.to_json` — Task 2 define, Tasks 8/9/11 consomem com esses nomes. ✓
- `buscar_descricao(job) -> tuple[str, bool]` — Task 6 define, Task 8 desempacota `(descricao, completo)`. ✓
- `provider.analisar(prompt) -> dict` — Task 5 define, Task 8 chama. ✓
- `analisar_vagas(jobs, hint)` — Task 8 define, Task 10 chama com `hint="dev"`. ✓
- `_bloco_analise(analise)` — Task 11 define e testa. ✓
- Tupla de `obter_vagas_pendentes_digest`: 7 campos após Task 9; Task 11 corrige os consumidores (`montar_digest`, `test_telegram`). ✓

Sem inconsistências.

---

## Execution Handoff

Plan completo e salvo em `docs/superpowers/plans/2026-09-06-agente-vagas.md`. Duas opções de execução:

1. **Subagent-Driven (recomendado)** — um subagente novo por task, revisão entre tasks, iteração rápida.
2. **Inline Execution** — executa as tasks nesta sessão com checkpoints de revisão.

Qual?
