"""The provider-neutral Study Agent Harness public package boundary."""

from importlib import import_module as _import_module

__version__ = "0.2.0"

__all__ = ("__version__", "api")

def __getattr__(name: str) -> object:
    if name == "api":
        return _import_module(f"{__name__}.api")
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(
        name
        for name in set(globals()) | set(__all__)
        if name.startswith("_") or name in __all__
    )
