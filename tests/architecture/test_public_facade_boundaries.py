from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

from study_agent import api

PROJECT_ROOT = Path(__file__).parents[2]
BLOCKED_PREFIXES = (
    "openai",
    "anthropic",
    "study_agent.adapters",
    "study_agent.cli",
    "study_agent.demo",
    "study_agent.filesystem",
    "study_agent.ui",
    "study_agent.telemetry",
    "fsrs",
)


def test_every_listed_subfacade_is_importable_without_optional_modules() -> None:
    expected_exports = {
        "runtime": {
            "EventSchema",
            "EventUpcasterRegistry",
            "KernelModule",
            "KernelModuleRegistry",
            "ModuleRegistry",
            "Registry",
        },
        "storage": {
            "Actor",
            "BlobStore",
            "Clock",
            "EventEnvelope",
            "EventSequenceConflictError",
            "EventStore",
            "IdFactory",
            "IdempotencyConflictError",
            "PrincipalKind",
            "Repository",
            "RunNotFoundError",
            "RunStore",
            "RunStoreConflictFailure",
        },
        "sources": {
            "BlobRef",
            "Citation",
            "DerivedRef",
            "FIGURE_CITATION_VERSION",
            "FigureCitationV1",
            "SourceRevision",
            "SourceRevisionRef",
            "SubstrateRef",
            "TEXT_CITATION_VERSION",
            "TextCitationV2",
            "citation_from_bytes",
            "citation_from_json",
        },
        "artifacts": {
            "AnswerBlock",
            "ArtifactBatchId",
            "ArtifactBatchRecord",
            "ArtifactCommandPort",
            "ArtifactContent",
            "ArtifactDecision",
            "ArtifactDecisionRecord",
            "ArtifactId",
            "ArtifactProposal",
            "ArtifactProposalOrigin",
            "ArtifactProvenance",
            "ArtifactProvenanceOrigin",
            "ArtifactReadDependency",
            "ArtifactRevisionId",
            "ArtifactRevisionRecord",
            "ArtifactRevisionStatus",
            "ArtifactSnapshot",
            "ArtifactViewPort",
            "AssessmentItemContent",
            "BlobRef",
            "Citation",
            "DerivedRef",
            "EvidenceObservation",
            "ExamBlueprintContent",
            "FigureCitationV1",
            "FlashcardContent",
            "GeneratedArtifactProvenance",
            "GeneratedBatchProofReceipt",
            "HybridFlashcardContent",
            "HumanAuthoredArtifactProvenance",
            "MorphologyFlashcardContent",
            "ServiceDecisionPolicyReceipt",
            "ServiceDecisionPolicyRequest",
            "SourceCommitment",
            "SourceRevision",
            "SourceRevisionRef",
            "StudyArtifactEnvelope",
            "StudyBriefContent",
            "StudyBriefSection",
            "SubstrateRef",
            "TextCitationV2",
            "VerifiedGeneratedArtifactBatch",
        },
        "assessments": {
            "AssessmentCommandPort",
            "AssessmentSnapshot",
            "AssessmentViewPort",
            "AttemptRecord",
            "CanonicalResponse",
            "CriterionResult",
            "DeterministicClosedGradingPolicyPort",
            "DeterministicGradeProvenance",
            "EvidenceDimension",
            "EvidenceDisposition",
            "FreeResponse",
            "GradeContestRecord",
            "GradeProvenance",
            "GradeRecord",
            "LearnerEvidenceEstimate",
            "LearnerEvidenceReference",
            "LearnerEvidenceViewPort",
            "LearnerPresentationView",
            "LearningEvidence",
            "MultipleChoiceResponse",
            "PresentationRecord",
            "RationalScore",
            "SingleChoiceResponse",
            "ValidatorReceipt",
            "VerifiedCapabilityGradeProvenance",
            "VerifiedGradePort",
            "canonical_multiple_choice",
            "response_fingerprint",
        },
        "recall": {
            "AppliedSchedule",
            "RecallCommandPort",
            "RecallRating",
            "RecallSnapshot",
            "RecallViewPort",
            "RecallViewRow",
            "RetentionObservation",
            "ReviewHistoryEntry",
            "ReviewRecord",
            "SchedulingPolicyConfigV1",
            "SchedulingPolicyPort",
            "SchedulingRequest",
            "SchedulingResult",
        },
    }
    for name in api.public_manifest().subfacades:
        module = __import__(f"study_agent.api.{name}", fromlist=["*"])
        expected = expected_exports.get(name, set())
        assert set(module.__all__) == expected
        assert {item for item in dir(module) if not item.startswith("_")} == expected


def test_pf07_facades_hide_lifecycle_implementation_details() -> None:
    for name in ("artifacts", "assessments", "recall"):
        module = __import__(f"study_agent.api.{name}", fromlist=["*"])
        public = set(module.__all__)
        assert not public & {
            "ArtifactService",
            "AssessmentService",
            "RecallService",
            "ProjectionArtifactView",
            "ProjectionAssessmentView",
            "ProjectionRecallView",
            "_LegacyEventStore",
            "_append_legacy",
        }
        assert all(not item.startswith("_") for item in public)


def test_root_import_stays_clean_when_optional_imports_are_unavailable() -> None:
    script = """
import builtins
import json
import sys

blocked = BLOCKED_MODULES
real_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if any(name == prefix or name.startswith(prefix + ".") for prefix in blocked):
        raise ModuleNotFoundError(name)
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
import study_agent
manifest = study_agent.api.public_manifest()
for name in manifest.subfacades:
    __import__(f"study_agent.api.{name}")

loaded = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in blocked)
)
print(json.dumps({"loaded": loaded, "fingerprint": manifest.fingerprint}))
""".replace("BLOCKED_MODULES", repr(BLOCKED_PREFIXES))
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    process = subprocess.run(
        (sys.executable, "-c", script),
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert process.stderr == ""
    result = json.loads(process.stdout)
    assert result["loaded"] == []
    assert result["fingerprint"] == api.public_manifest().fingerprint


def test_canonical_event_store_and_domain_upcast_surface_are_public() -> None:
    import study_agent.ports as ports
    from study_agent.api.runtime import EventUpcasterRegistry

    assert "EventStore" in ports.__all__
    assert hasattr(ports, "EventStore")
    annotations = inspect.signature(EventUpcasterRegistry.upcast).parameters["event"].annotation
    assert "DomainEvent" not in str(annotations)


def test_capability_facade_hides_internal_termination_observation() -> None:
    import study_agent.api.capabilities as capabilities

    assert not hasattr(capabilities, "TerminatedCapabilityOutcome")
    assert "TerminatedCapabilityOutcome" not in capabilities.__all__
