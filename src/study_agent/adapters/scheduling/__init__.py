"""Optional scheduling integrations.

The package itself is dependency-free.  Concrete scheduler modules load their
third-party package lazily so importing the harness without optional extras
remains safe.
"""

from .py_fsrs import (
    FSRS_ADAPTER_POLICY_ID,
    FSRS_ADAPTER_POLICY_VERSION,
    FSRS_CONFIGURATION_FINGERPRINT,
    FSRS_IMPLEMENTATION_ID,
    FSRS_IMPLEMENTATION_VERSION,
    FsrsAdapterError,
    FsrsUnavailableError,
    PyFsrsSchedulingPolicy,
)

__all__ = [
    "FSRS_ADAPTER_POLICY_ID",
    "FSRS_ADAPTER_POLICY_VERSION",
    "FSRS_CONFIGURATION_FINGERPRINT",
    "FSRS_IMPLEMENTATION_ID",
    "FSRS_IMPLEMENTATION_VERSION",
    "FsrsAdapterError",
    "FsrsUnavailableError",
    "PyFsrsSchedulingPolicy",
]
