from abc import ABC, abstractmethod


class BaseLLMBackend(ABC):
    """Interfaz abstracta para backends de LLM."""

    @abstractmethod
    def ask(self, pregunta: str, historial: list[dict], contexto: str, org_name: str) -> str:
        """Envía la pregunta al LLM con contexto e historial. Retorna la respuesta."""
        ...


class LLMError(Exception):
    """Error al llamar al LLM."""
    pass
