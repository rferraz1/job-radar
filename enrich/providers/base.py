from abc import ABC, abstractmethod


class LLMIndisponivel(Exception):
    """Falha dura: rede, autenticação, rate-limit. Ciclo deve parar de chamar o LLM."""


class LLMRespostaInvalida(Exception):
    """Modelo respondeu, mas não foi possível extrair JSON válido após retry."""


class LLMProvider(ABC):
    @abstractmethod
    def analisar(self, prompt: str) -> dict:
        ...
