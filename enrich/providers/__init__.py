from .base import LLMProvider, LLMIndisponivel, LLMRespostaInvalida

__all__ = ["LLMProvider", "LLMIndisponivel", "LLMRespostaInvalida", "obter_provider"]


def obter_provider(nome: str | None = None) -> LLMProvider:
    from config import LLM_PROVIDER
    nome = (nome or LLM_PROVIDER).lower()
    if nome == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider()
    raise LLMIndisponivel(f"LLM_PROVIDER desconhecido: {nome!r}")
