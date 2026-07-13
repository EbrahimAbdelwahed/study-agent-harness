"""Pure lifecycle desired-intent contracts."""

from .contracts import (
    MANIFEST_SCHEMA_VERSION,
    DesiredCourse,
    DesiredRepository,
    DesiredSource,
    LifecycleManifestV1,
    ManifestValidationError,
    manifest_schema,
)

__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "DesiredCourse",
    "DesiredRepository",
    "DesiredSource",
    "LifecycleManifestV1",
    "ManifestValidationError",
    "manifest_schema",
]
