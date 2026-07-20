"""Shared validation for provider-neutral portable contracts."""

from __future__ import annotations

import re
from collections.abc import Mapping

from study_agent.domain._validation import JsonValue

_FORBIDDEN_SELECTOR_KEYS = frozenset(
    {
        "model",
        "model_id",
        "model_name",
        "provider",
        "provider_id",
        "provider_name",
        "vendor",
        "vendor_id",
        "vendor_name",
    }
)


def reject_provider_selectors(value: JsonValue, path: str) -> None:
    """Reject transport selection while permitting model input/output data."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            reject_provider_selector_name(key, f"{path}.{key}")
            reject_provider_selectors(item, f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            reject_provider_selectors(item, f"{path}[{index}]")


def reject_provider_selector_name(value: str, path: str) -> None:
    """Reject a provider/model selector in a key-like portable name."""

    acronym_split = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", acronym_split)
    normalized = re.sub(r"[^a-z0-9]+", "_", camel_split.lower()).strip("_")
    if normalized in {"model_input", "model_output"}:
        return
    tokens = frozenset(normalized.split("_"))
    if normalized in _FORBIDDEN_SELECTOR_KEYS or tokens & {
        "model",
        "provider",
        "vendor",
    }:
        raise ValueError(f"{path} is provider/model-specific")


__all__ = ["reject_provider_selector_name", "reject_provider_selectors"]
