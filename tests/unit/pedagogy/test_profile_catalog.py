from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

import pytest

from study_agent.domain import InteractionId, PrincipalKind, RevisionId
from study_agent.domain._validation import JsonObject
from study_agent.pedagogy import (
    HYBRID_MACRO_DETAIL_DESCRIPTOR,
    HYBRID_MACRO_DETAIL_V1,
    MORPHOLOGY_FIRST_ANATOMY_DESCRIPTOR,
    MORPHOLOGY_FIRST_ANATOMY_V1,
    PEDAGOGICAL_PROFILE_CATALOG,
    PedagogicalProfileDescriptor,
    PedagogicalProfileId,
    PedagogicalProfileRef,
    ProfileSelectionBasis,
    ProfileSelectionMode,
    ProfileSelectionReceipt,
    ProfileSelectorKind,
)


def _default() -> ProfileSelectionReceipt:
    return ProfileSelectionReceipt(
        HYBRID_MACRO_DETAIL_V1,
        ProfileSelectionMode.DEFAULT,
        ProfileSelectorKind.HOST,
        PrincipalKind.SERVICE,
        ProfileSelectionBasis(),
    )


def _explicit_morphology() -> ProfileSelectionReceipt:
    return ProfileSelectionReceipt(
        MORPHOLOGY_FIRST_ANATOMY_V1,
        ProfileSelectionMode.EXPLICIT_REQUEST,
        ProfileSelectorKind.HUMAN,
        PrincipalKind.HUMAN,
        ProfileSelectionBasis(interaction_id=InteractionId("interaction-learner-1")),
    )


def _trusted_morphology() -> ProfileSelectionReceipt:
    return ProfileSelectionReceipt(
        MORPHOLOGY_FIRST_ANATOMY_V1,
        ProfileSelectionMode.TRUSTED_METADATA,
        ProfileSelectorKind.TRUSTED_MATERIAL,
        PrincipalKind.SERVICE,
        ProfileSelectionBasis(source_revision_id=RevisionId("revision-anatomy-1")),
    )


def test_catalog_is_closed_deterministic_immutable_and_defaults_to_hybrid() -> None:
    catalog = PEDAGOGICAL_PROFILE_CATALOG
    discovered = catalog.list()

    assert isinstance(discovered, tuple)
    assert tuple(item.ref.identity for item in discovered) == (
        "hybrid-macro-detail@1",
        "morphology-first-anatomy@1",
    )
    assert catalog.list() == discovered
    assert catalog.default == HYBRID_MACRO_DETAIL_V1
    assert catalog.resolve(HYBRID_MACRO_DETAIL_V1) is HYBRID_MACRO_DETAIL_DESCRIPTOR
    assert (
        catalog.resolve(MORPHOLOGY_FIRST_ANATOMY_V1)
        is MORPHOLOGY_FIRST_ANATOMY_DESCRIPTOR
    )
    assert not hasattr(catalog, "register")

    with pytest.raises(ValueError, match="unknown pedagogical profile"):
        catalog.resolve(PedagogicalProfileRef(PedagogicalProfileId.HYBRID_MACRO_DETAIL, 2))
    with pytest.raises((FrozenInstanceError, AttributeError)):
        cast(object, discovered[0]).hard_ceiling = 99  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "receipt",
    (_default(), _explicit_morphology(), _trusted_morphology()),
    ids=("default", "explicit", "trusted-metadata"),
)
def test_selection_receipts_round_trip_exact_auditable_basis(
    receipt: ProfileSelectionReceipt,
) -> None:
    assert ProfileSelectionReceipt.from_json(receipt.to_json()) == receipt
    assert ProfileSelectionReceipt.from_bytes(receipt.to_bytes()) == receipt
    assert set(receipt.to_json()) == {
        "profile",
        "mode",
        "selector_kind",
        "selector_authority",
        "basis",
    }
    with pytest.raises(TypeError):
        receipt.to_json()["mode"] = "forged"  # type: ignore[index]


def test_morphology_requires_trusted_basis_and_model_cannot_select() -> None:
    factories: tuple[Callable[[], object], ...] = (
        lambda: ProfileSelectionReceipt(
            MORPHOLOGY_FIRST_ANATOMY_V1,
            ProfileSelectionMode.DEFAULT,
            ProfileSelectorKind.HOST,
            PrincipalKind.SERVICE,
            ProfileSelectionBasis(),
        ),
        lambda: ProfileSelectionReceipt(
            MORPHOLOGY_FIRST_ANATOMY_V1,
            ProfileSelectionMode.EXPLICIT_REQUEST,
            ProfileSelectorKind.HUMAN,
            PrincipalKind.HUMAN,
            ProfileSelectionBasis(),
        ),
        lambda: ProfileSelectionReceipt(
            MORPHOLOGY_FIRST_ANATOMY_V1,
            ProfileSelectionMode.TRUSTED_METADATA,
            ProfileSelectorKind.TRUSTED_MATERIAL,
            PrincipalKind.SERVICE,
            ProfileSelectionBasis(),
        ),
        lambda: ProfileSelectionReceipt(
            HYBRID_MACRO_DETAIL_V1,
            ProfileSelectionMode.DEFAULT,
            ProfileSelectorKind.HOST,
            PrincipalKind.MODEL,
            ProfileSelectionBasis(),
        ),
        lambda: ProfileSelectionBasis(
            interaction_id=cast(InteractionId, "model-output")
        ),
        lambda: ProfileSelectionBasis(
            source_revision_id=cast(RevisionId, "course-title-anatomy")
        ),
    )
    for factory in factories:
        with pytest.raises((TypeError, ValueError)):
            factory()


def test_unknown_versions_course_title_and_model_output_fail_closed() -> None:
    payload = dict(_explicit_morphology().to_json())
    profile = dict(cast(JsonObject, payload["profile"]))
    profile["version"] = 2
    payload["profile"] = profile
    with pytest.raises(ValueError, match="unknown pedagogical profile"):
        ProfileSelectionReceipt.from_json(payload)

    for field in ("course_title", "model_output"):
        forged = dict(_explicit_morphology().to_json())
        forged[field] = "Anatomy"
        with pytest.raises(ValueError):
            ProfileSelectionReceipt.from_json(forged)

    assert tuple(ProfileSelectorKind) == (
        ProfileSelectorKind.HOST,
        ProfileSelectorKind.HUMAN,
        ProfileSelectorKind.TRUSTED_MATERIAL,
    )


def test_descriptors_expose_budget_roles_grounding_tradeoffs_and_neutrality() -> None:
    hybrid = HYBRID_MACRO_DETAIL_DESCRIPTOR
    morphology = MORPHOLOGY_FIRST_ANATOMY_DESCRIPTOR

    assert hybrid.recommended_ceiling_range == (16, 22)
    assert hybrid.hard_ceiling == 24
    assert hybrid.ordered_roles == ("overview", "section", "detail")
    assert morphology.recommended_ceiling_range is None
    assert morphology.hard_ceiling == 24
    assert morphology.ordered_roles == (
        "macro_reconstruction",
        "atomic_discrimination",
    )
    assert morphology.macro_to_atomic_maximum == 3

    hybrid_guidance = repr(hybrid.to_json()).lower()
    morphology_guidance = repr(morphology.to_json()).lower()
    for token in ("default", "general medical", "framework", "detail", "ceilings"):
        assert token in hybrid_guidance
    for token in (
        "explicitly requested",
        "trusted material metadata",
        "spatial reconstruction",
        "discriminations",
        "source linkage",
    ):
        assert token in morphology_guidance
    for guidance in (hybrid_guidance, morphology_guidance):
        assert "deck" in guidance and "raw html" in guidance
        assert not any(
            token in guidance
            for token in ("openai", "deepseek", "anthropic", "api_key", "credential")
        )

    forbidden_fields = {
        "provider",
        "model",
        "runtime",
        "deck",
        "tags",
        "learner_preferences",
    }
    assert forbidden_fields.isdisjoint(
        field.name for field in fields(PedagogicalProfileDescriptor)
    )
