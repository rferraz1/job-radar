# enrich/analyze.py
from datetime import date

from logger import get_logger
from .baseline import carregar_cv
from .fetch_detail import buscar_descricao
from .models import Analysis
from .prompt import montar_prompt
from .providers import obter_provider
from .providers.base import LLMIndisponivel, LLMRespostaInvalida

logger = get_logger()


def _latch_chave() -> str:
    return f"llm_off_{date.today().isoformat()}"


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


def analisar_vagas(jobs: list, hint: str = "dev", perfil_chave: str = "", hint_fn=None) -> None:
    """Preenche job.analise in-place. Garantia central da branch: uma falha
    de LLM (ou qualquer erro inesperado no enrich) NUNCA derruba o ciclo nem
    dropa vaga — no pior caso todas ficam com analise=None e o routing cai no
    fallback heurístico.

    `perfil_chave` é aceito por simetria com o resto do pipeline (o latch é
    global, não por perfil — a quota do LLM é da conta inteira).
    `hint_fn(job) -> str` calcula a trilha por vaga; default = `hint` fixo.
    """
    if not jobs:
        return
    import config
    from database.database import definir_metadado, obter_metadado

    chave = _latch_chave()

    # I3: latch diário. Uma vez que a quota estourou hoje, o resto do dia é
    # só heurística (volta amanhã) — nem constrói provider.
    try:
        if obter_metadado(chave):
            logger.warning(
                "[analyze] latch diário de LLM ativo — ciclo sem análise LLM, fallback heurístico."
            )
            return
    except Exception as e:
        logger.warning(f"[analyze] falha ao ler latch de LLM ({type(e).__name__}: {e}) — seguindo.")

    # I4 + C1: CV é a base da compatibilidade. Sem CV (path errado, erro de
    # I/O), o modelo chutaria score só pelo título — e score roteia alerta
    # imediato. Melhor não analisar.
    try:
        cv_text = carregar_cv()
    except Exception as e:
        logger.warning(
            f"[analyze] falha ao carregar CV ({type(e).__name__}: {e}) — tratando como CV vazio."
        )
        cv_text = ""
    if not cv_text or not cv_text.strip():
        from config import CV_PATH

        logger.error(
            f"[analyze] CV vazio em {CV_PATH} — ciclo sem análise LLM, fallback heurístico"
        )
        return

    # C1: qualquer erro construindo o provider (ModuleNotFoundError de um
    # google-genai quebrado, etc.) não pode subir pro ciclo.
    try:
        provider = obter_provider()
    except LLMIndisponivel as e:
        logger.warning(
            f"[analyze] provider indisponível ({e}) — ciclo sem análise LLM, fallback heurístico."
        )
        return
    except Exception as e:
        logger.warning(
            f"[analyze] erro ao construir provider ({type(e).__name__}: {e}) — "
            "ciclo sem análise LLM, fallback heurístico."
        )
        return

    if hint_fn is None:
        hint_fn = lambda job: hint  # noqa: E731

    falhas_seguidas = 0
    analisadas = 0
    for job in jobs:
        try:
            job.analise = analisar_vaga(job, cv_text, provider, hint_fn(job))
            falhas_seguidas = 0
            if job.analise:
                analisadas += 1
        except LLMIndisponivel as e:
            falhas_seguidas += 1
            logger.warning(
                f"[analyze] LLM indisponível ({falhas_seguidas}/{config.ENRICH_MAX_FALHAS_LLM}): {e}"
            )
            job.analise = None
            if falhas_seguidas >= config.ENRICH_MAX_FALHAS_LLM:
                logger.warning(
                    "[analyze] limite de falhas atingido — LLM desligado pelo resto do dia."
                )
                try:
                    definir_metadado(chave, "1")
                except Exception as e2:
                    logger.warning(
                        f"[analyze] falha ao gravar latch de LLM ({type(e2).__name__}: {e2})."
                    )
                return
        except Exception as e:
            # C1: erro inesperado numa vaga (não LLMIndisponivel/
            # LLMRespostaInvalida, que analisar_vaga já trata) — loga, deixa
            # essa vaga sem análise e segue pras próximas.
            logger.warning(
                f"[analyze] erro inesperado analisando "
                f"'{getattr(job, 'titulo', '?')}' ({type(e).__name__}: {e}) — segue sem análise."
            )
            job.analise = None
    logger.info(f"[analyze] {analisadas}/{len(jobs)} vaga(s) analisadas pelo LLM.")
