"""Curated, provider-neutral public facade for the Study Agent Harness."""

from importlib import import_module as _import_module

from .manifest import _EXPORTS as _PUBLIC_EXPORTS
from .manifest import _SUBFACADES as _PUBLIC_SUBFACADES
from .manifest import PublicManifest, public_manifest

# Importing a submodule necessarily gives the package an implementation-module
# attribute. Keep that loader detail out of the curated public namespace.
globals().pop("manifest", None)

__all__ = ("PublicManifest", "public_manifest", *_PUBLIC_SUBFACADES)
if __all__ != _PUBLIC_EXPORTS:  # pragma: no cover - an internal contract guard
    raise RuntimeError("public facade exports do not match its manifest")


def __getattr__(name: str) -> object:
    if name in _PUBLIC_SUBFACADES:
        return _import_module(f"{__name__}.{name}")
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(
        name for name in set(globals()) | set(__all__) if name.startswith("_") or name in __all__
    )
