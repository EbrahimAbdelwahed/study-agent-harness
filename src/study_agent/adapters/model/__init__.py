"""Provider-neutral scripted and generic HTTP model adapters."""

from .openai_compatible import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    HttpResponse,
    HttpTransport,
    OpenAICompatibleConfig,
    OpenAICompatibleModel,
    StdlibHttpTransport,
)
from .scripted import ScriptedExchange, ScriptedModel

__all__ = [
    "ADAPTER_ID",
    "ADAPTER_VERSION",
    "HttpResponse",
    "HttpTransport",
    "OpenAICompatibleConfig",
    "OpenAICompatibleModel",
    "ScriptedExchange",
    "ScriptedModel",
    "StdlibHttpTransport",
]
