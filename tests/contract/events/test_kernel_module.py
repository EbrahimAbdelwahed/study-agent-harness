import pytest

from study_agent.domain.errors import ConflictFailure, ValidationFailure
from study_agent.kernel.module import EventSchema, KernelModule, KernelModuleRegistry


def module(module_id: str, event_type: str = "cardine.card.created") -> KernelModule:
    return KernelModule(
        module_id=module_id,
        version="1",
        event_schemas={event_type: 1},  # type: ignore[arg-type]
        reducers=((f"{event_type}@1", object()),),
        projections=((f"{event_type}@1", object()),),
        services=((f"{module_id}.service", object()),),
        capabilities=((f"{module_id}.capability", object()),),
    )


def test_module_is_immutable_and_registry_is_deterministically_closed() -> None:
    registry = KernelModuleRegistry()
    registry.register(module("z-module"))
    registry.register(module("a-module", "cardine.card.reviewed"))
    registry.close()
    assert tuple(item.module_id for item in registry.snapshot()) == ("a-module", "z-module")
    with pytest.raises(ValidationFailure):
        registry.register(module("late"))


def test_module_collisions_and_unknown_schemas_fail_closed() -> None:
    registry = KernelModuleRegistry()
    registry.register(module("one"))
    with pytest.raises(ConflictFailure):
        registry.register(module("two"))

    unknown = KernelModule(
        module_id="unknown",
        version="1",
        event_schemas=(EventSchema("cardine.card.created", 1),),
        reducers=(("cardine.card.missing@1", object()),),
    )
    registry = KernelModuleRegistry()
    registry.register(unknown)
    with pytest.raises(ValidationFailure):
        registry.close()


def test_event_schema_rejects_duplicates() -> None:
    with pytest.raises(ConflictFailure):
        KernelModule(
            module_id="dup",
            version="1",
            event_schemas=(
                EventSchema("cardine.card.created", 1),
                EventSchema("cardine.card.created", 1),
            ),
        )
