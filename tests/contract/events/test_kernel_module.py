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


def test_cross_module_event_type_ownership_rejects_historical_version_collision() -> None:
    registry = KernelModuleRegistry()
    registry.register(module("one", "cardine.card.created"))
    with pytest.raises(ConflictFailure):
        registry.register(
            KernelModule(
                module_id="two",
                version="1",
                event_schemas=(EventSchema("cardine.card.created", 2),),
            )
        )


def test_closed_snapshot_compiles_callable_schema_reducer_and_upcaster() -> None:
    def decode(payload: object) -> object:
        return payload

    def reduce(state: object, _event: object, _payload: object) -> dict[str, object]:
        return {"ready": True}

    registry = KernelModuleRegistry()
    registry.register(
        KernelModule(
            module_id="compiled",
            version="1",
            event_schemas=(
                EventSchema("cardine.card.created", 1, decode),
                EventSchema("cardine.card.created", 2, decode),
            ),
            reducers=(
                ("cardine.card.created@1", reduce),
                ("cardine.card.created@2", reduce),
            ),
            upcasters=(("cardine.card.created@1", lambda payload: payload),),
        )
    )
    registry.close()
    snapshot = registry.compile()
    assert not hasattr(snapshot, "event_registry")
    assert not hasattr(snapshot, "upcasters")
    with pytest.raises(ValidationFailure):
        registry.register(module("late", "cardine.card.late"))
