"""Immutable module values and deterministic explicit registration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from study_agent.domain._validation import JsonObject
from study_agent.domain.errors import ConflictFailure, ValidationFailure
from study_agent.domain.events import validate_event_type

if TYPE_CHECKING:
    from study_agent.events.upcasting import EventUpcasterRegistry
    from study_agent.state.registry import EventRegistry


def _name(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValidationFailure(f"{field_name} must be non-empty and trimmed")
    return value


@dataclass(frozen=True, slots=True)
class EventSchema:
    event_type: str
    schema_version: int
    decoder: Callable[[JsonObject], object] | None = field(
        default=None, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        try:
            validate_event_type(self.event_type)
        except ValidationFailure as error:
            raise ValidationFailure(str(error)) from error
        if type(self.schema_version) is not int or self.schema_version < 1:
            raise ValidationFailure("schema version must be positive")
        if self.decoder is not None and not callable(self.decoder):
            raise ValidationFailure("event schema decoder must be callable")

    @property
    def key(self) -> tuple[str, int]:
        return self.event_type, self.schema_version


def _freeze_mapping(value: Mapping[str, object] | None) -> tuple[tuple[str, object], ...]:
    if value is None:
        return ()
    items: list[tuple[str, object]] = []
    for key, item in value.items():
        items.append((_name(key, "registration name"), item))
    return tuple(sorted(items, key=lambda pair: pair[0]))


@dataclass(frozen=True, slots=True)
class KernelModule:
    module_id: str
    version: str
    event_schemas: tuple[EventSchema, ...] = ()
    reducers: tuple[tuple[str, object], ...] = ()
    projections: tuple[tuple[str, object], ...] = ()
    services: tuple[tuple[str, object], ...] = ()
    capabilities: tuple[tuple[str, object], ...] = ()
    upcasters: tuple[tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        _name(self.module_id, "module_id")
        _name(self.version, "module version")
        if isinstance(self.event_schemas, Mapping):
            converted: list[EventSchema] = []
            for event_type, value in self.event_schemas.items():
                if isinstance(value, EventSchema):
                    schema = value
                elif isinstance(value, int):
                    schema = EventSchema(event_type, value)
                elif isinstance(value, Mapping):
                    schema = EventSchema(
                        event_type,
                        value.get("schema_version", value.get("version", 0)),
                        value.get("decoder"),
                    )
                else:
                    raise ValidationFailure("event_schemas must contain schema versions")
                converted.append(schema)
            schemas = tuple(converted)
        else:
            schemas = tuple(self.event_schemas)
        if any(not isinstance(schema, EventSchema) for schema in schemas):
            raise ValidationFailure("event_schemas must contain EventSchema values")
        if len({schema.key for schema in schemas}) != len(schemas):
            raise ConflictFailure("duplicate event schema in module")
        object.__setattr__(
            self, "event_schemas", tuple(sorted(schemas, key=lambda schema: schema.key))
        )
        for field_name in (
            "reducers",
            "projections",
            "services",
            "capabilities",
            "upcasters",
        ):
            raw = getattr(self, field_name)
            if isinstance(raw, Mapping):
                normalized = _freeze_mapping(raw)
            else:
                try:
                    pairs = tuple(raw)
                    normalized = tuple(sorted(pairs, key=lambda pair: pair[0]))
                    if any(not isinstance(pair, tuple) or len(pair) != 2 for pair in normalized):
                        raise ValueError
                    normalized = tuple(
                        (_name(name, "registration name"), value)
                        for name, value in normalized
                    )
                except (TypeError, ValueError, IndexError) as error:
                    raise ValidationFailure(
                        f"{field_name} must contain named registrations"
                    ) from error
            object.__setattr__(self, field_name, normalized)


@dataclass(frozen=True, slots=True)
class KernelSnapshot:
    """Closed module metadata compiled into immutable runtime registries."""

    modules: tuple[KernelModule, ...]
    event_registry: EventRegistry
    upcasters: EventUpcasterRegistry


class KernelModuleRegistry:
    """Host-owned, explicit module registry with a closed runtime snapshot."""

    def __init__(self) -> None:
        self._modules: dict[str, KernelModule] = {}
        self._closed = False
        self._compiled: KernelSnapshot | None = None

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def modules(self) -> tuple[KernelModule, ...]:
        return tuple(self._modules[key] for key in sorted(self._modules))

    def register(self, module: KernelModule) -> None:
        if self._closed:
            raise ValidationFailure("kernel module registration is closed")
        if not isinstance(module, KernelModule):
            raise ValidationFailure("module registration requires KernelModule")
        if module.module_id in self._modules:
            raise ConflictFailure("kernel module already registered")
        existing_schemas = {
            schema.key for item in self._modules.values() for schema in item.event_schemas
        }
        if existing_schemas.intersection(schema.key for schema in module.event_schemas):
            raise ConflictFailure("event schema registration collides")
        existing_event_types = {
            schema.event_type
            for item in self._modules.values()
            for schema in item.event_schemas
        }
        if existing_event_types.intersection(
            schema.event_type for schema in module.event_schemas
        ):
            raise ConflictFailure("event type ownership collides")
        self._ensure_unique_names(module, "reducers")
        self._ensure_unique_names(module, "projections")
        self._ensure_unique_names(module, "services")
        self._ensure_unique_names(module, "capabilities")
        self._modules[module.module_id] = module

    register_module = register

    def close(self) -> KernelModuleRegistry:
        self._validate_dependencies()
        self._compiled = self.compile()
        self._closed = True
        return self

    freeze = close

    def snapshot(self) -> tuple[KernelModule, ...]:
        if not self._closed:
            raise ValidationFailure("kernel module registry is not closed")
        return self.modules

    def compile(self) -> KernelSnapshot:
        """Compile registered metadata into closed reducer/upcaster registries."""
        if self._closed and self._compiled is not None:
            return self._compiled
        self._validate_dependencies()
        from study_agent.events.upcasting import EventUpcasterRegistry
        from study_agent.state.registry import EventRegistry

        upcasters = EventUpcasterRegistry()
        for module in self.modules:
            for name, candidate in module.upcasters:
                event_type, separator, version = name.rpartition("@")
                if not separator or not version.isdigit() or not callable(candidate):
                    raise ValidationFailure("upcaster registration is invalid")
                upcasters.register(event_type, int(version), candidate)

        event_registry = EventRegistry(upcasters)
        for module in self.modules:
            reducers = dict(module.reducers)
            for schema in module.event_schemas:
                reducer = reducers.get(f"{schema.event_type}@{schema.schema_version}")
                if schema.decoder is None and reducer is None:
                    continue
                if not callable(schema.decoder) or not callable(reducer):
                    # A module may publish schema metadata before attaching a
                    # projection owner.  Only a complete callable pair enters
                    # the executable EventRegistry.
                    continue
                event_registry.register_erased(
                    schema.event_type,
                    schema.schema_version,
                    schema.decoder,
                    reducer,
                )
        upcasters.close()
        event_registry.close()
        return KernelSnapshot(self.modules, event_registry, upcasters)

    compiled_snapshot = compile

    def _ensure_unique_names(self, module: KernelModule, field_name: str) -> None:
        names = [name for name, _ in getattr(module, field_name)]
        if len(names) != len(set(names)):
            raise ConflictFailure(f"duplicate {field_name} registration")
        existing = {
            name for item in self._modules.values() for name, _ in getattr(item, field_name)
        }
        if existing.intersection(names):
            raise ConflictFailure(f"{field_name} registration collides")

    def _validate_dependencies(self) -> None:
        schema_keys = {
            schema.key for module in self._modules.values() for schema in module.event_schemas
        }
        for module in self._modules.values():
            for name, _ in module.reducers + module.projections:
                event_name, separator, version = name.rpartition("@")
                if separator:
                    if not version.isdigit() or (event_name, int(version)) not in schema_keys:
                        raise ValidationFailure("registration references an unknown event schema")
                elif not any(schema[0] == name for schema in schema_keys):
                    raise ValidationFailure("registration references an unknown event schema")
            for name, _ in module.upcasters:
                event_name, separator, version = name.rpartition("@")
                if (
                    not separator
                    or not version.isdigit()
                    or (event_name, int(version)) not in schema_keys
                ):
                    raise ValidationFailure("upcaster references an unknown event schema")


ModuleRegistry = KernelModuleRegistry
