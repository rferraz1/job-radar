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
