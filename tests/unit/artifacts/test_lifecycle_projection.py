from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from study_agent.artifacts import (
    artifact_batch_id_for,
    human_authored_artifact_batch_id_for,
)
from study_agent.artifacts.contracts import ArtifactProposalOrigin
from study_agent.artifacts.events import RecordedArtifactProposal
from study_agent.artifacts.projection import register_artifact_events
from study_agent.domain import (
    ArtifactDecision,
    ArtifactRevisionStatus,
    InteractionKind,
    PrincipalKind,
    RunId,
)
from study_agent.domain._validation import JsonObject
from study_agent.state import EventRegistry, Projection, apply_event
from tests.unit.artifacts.test_lifecycle_events import (
    CHUNK,
    COMMITMENT,
    COURSE,
    INTERACTION,
    REVISION,
    RUN,
    SESSION,
    SOURCE,
    content,
    decision_event,
    generated_provenance,
    human_provenance,
    proposal_event,
    recorded,
)


def base_state() -> JsonObject:
    return {
        "course": {"course_id": str(COURSE)},
        "sessions": {
            str(SESSION): {
                "session_id": str(SESSION),
                "course_id": str(COURSE),
            }
        },
        "session_interactions": {
            str(INTERACTION): {
                "session_id": str(SESSION),
                "kind": InteractionKind.HUMAN.value,
            }
        },
        "sources": {
            str(SOURCE): {
                "source_id": str(SOURCE),
                "revisions": {str(REVISION): {"revision_id": str(REVISION)}},
            }
        },
        "chunks": {
            str(CHUNK): {
                "chunk_id": str(CHUNK),
                "source_id": str(SOURCE),
                "revision_id": str(REVISION),
                "start_offset": 0,
                "end_offset": 64,
            }
        },
    }


def registry() -> EventRegistry:
    value = EventRegistry()
    register_artifact_events(value)
    return value


def proposed_pair() -> tuple[
    Projection, RecordedArtifactProposal, RecordedArtifactProposal
]:
    batch = artifact_batch_id_for(COURSE, SESSION, RUN, "pair")
    framework_content = content(text="Three-cusp framework")
    framework = recorded(
        0,
        batch_id=batch,
        envelope=framework_content,
        provenance=generated_provenance(framework_content),
    )
    detail_content = content(parent_ordinal=0, text="Right coronary cusp")
    detail = recorded(
        1,
        batch_id=batch,
        envelope=detail_content,
        provenance=generated_provenance(detail_content),
        parent_artifact_id=framework.artifact_id,
    )
    event = proposal_event(proposals=(framework, detail), key="pair")
    projection = apply_event(Projection(COURSE, 1, base_state()), event, registry())
    return projection, framework, detail


def test_replay_records_atomic_batch_statuses_and_lower_parent_resolution() -> None:
    projection, framework, detail = proposed_pair()
    state = cast(JsonObject, projection.state["study_artifacts"])
    revisions = cast(JsonObject, state["revisions"])
    artifacts = cast(JsonObject, state["artifacts"])

    assert tuple(cast(JsonObject, state["batches"]))
    assert cast(JsonObject, revisions[str(framework.revision_id)])["status"] == (
        ArtifactRevisionStatus.PROPOSED.value
    )
    detail_record = cast(JsonObject, revisions[str(detail.revision_id)])
    assert detail_record["parent_artifact_id"] == str(framework.artifact_id)
    assert cast(JsonObject, artifacts[str(detail.artifact_id)])["parent_artifact_id"] == str(
        framework.artifact_id
    )


@pytest.mark.parametrize("hostile", ("missing_source", "wrong_revision", "wrong_chunk", "span"))
def test_hostile_replay_rejects_noncanonical_source_revision_chunk_and_span(
    hostile: str,
) -> None:
    state = dict(base_state())
    if hostile == "missing_source":
        state["sources"] = {}
    elif hostile == "wrong_revision":
        source = dict(cast(JsonObject, cast(JsonObject, state["sources"])[str(SOURCE)]))
        source["revisions"] = {"other-revision": {}}
        state["sources"] = {str(SOURCE): source}
    elif hostile == "wrong_chunk":
        chunk = dict(cast(JsonObject, cast(JsonObject, state["chunks"])[str(CHUNK)]))
        chunk["source_id"] = "other-source"
        state["chunks"] = {str(CHUNK): chunk}
    else:
        chunk = dict(cast(JsonObject, cast(JsonObject, state["chunks"])[str(CHUNK)]))
        chunk["end_offset"] = COMMITMENT.end_offset - 1
        state["chunks"] = {str(CHUNK): chunk}

    with pytest.raises(ValueError, match=r"source|revision|chunk|span"):
        apply_event(Projection(COURSE, 1, cast(JsonObject, state)), proposal_event(), registry())


def test_human_origin_requires_exact_same_session_human_interaction_on_replay() -> None:
    batch = human_authored_artifact_batch_id_for(COURSE, SESSION, INTERACTION, "human")
    envelope = content(text="Human-authored wording")
    proposal = recorded(
        batch_id=batch,
        envelope=envelope,
        provenance=human_provenance(),
    )
    event = proposal_event(
        actor=PrincipalKind.HUMAN,
        proposals=(proposal,),
        origin=ArtifactProposalOrigin.HUMAN_AUTHORED,
        key="human",
    )
    for interaction in (
        {},
        {str(INTERACTION): {"session_id": "other-session", "kind": "human"}},
        {str(INTERACTION): {"session_id": str(SESSION), "kind": "model"}},
    ):
        state = dict(base_state())
        state["session_interactions"] = interaction
        with pytest.raises(ValueError, match="human interaction"):
            apply_event(Projection(COURSE, 1, cast(JsonObject, state)), event, registry())


def test_terminal_decisions_exact_supersession_and_durable_parent_across_batches() -> None:
    projection, framework, detail = proposed_pair()
    projection = apply_event(
        projection,
        replace(
            decision_event(detail.revision_id, ArtifactDecision.ACCEPT, key="accept-old"),
            course_sequence=3,
        ),
        registry(),
    )

    human_batch = human_authored_artifact_batch_id_for(
        COURSE, SESSION, INTERACTION, "human-revision"
    )
    revised_content = content(text="Human revision of right cusp")
    human_revision = recorded(
        batch_id=human_batch,
        envelope=revised_content,
        provenance=human_provenance(prior=detail.revision_id),
        artifact_id=detail.artifact_id,
        prior=detail.revision_id,
        parent_artifact_id=framework.artifact_id,
    )
    projection = apply_event(
        projection,
        replace(
            proposal_event(
                actor=PrincipalKind.HUMAN,
                proposals=(human_revision,),
                origin=ArtifactProposalOrigin.HUMAN_AUTHORED,
                key="human-revision",
            ),
            course_sequence=4,
        ),
        registry(),
    )
    projection = apply_event(
        projection,
        replace(
            decision_event(
                human_revision.revision_id,
                ArtifactDecision.ACCEPT,
                supersedes=detail.revision_id,
                key="accept-new",
            ),
            course_sequence=5,
        ),
        registry(),
    )
    revisions = cast(
        JsonObject, cast(JsonObject, projection.state["study_artifacts"])["revisions"]
    )
    old = cast(JsonObject, revisions[str(detail.revision_id)])
    new = cast(JsonObject, revisions[str(human_revision.revision_id)])
    assert old["status"] == ArtifactRevisionStatus.SUPERSEDED.value
    assert new["status"] == ArtifactRevisionStatus.ACCEPTED.value
    assert new["parent_artifact_id"] == str(framework.artifact_id)

    with pytest.raises(ValueError, match="terminal"):
        apply_event(
            projection,
            replace(
                decision_event(
                    human_revision.revision_id,
                    ArtifactDecision.REJECT,
                    key="decide-again",
                ),
                course_sequence=6,
            ),
            registry(),
        )

    later_run = RunId("run-later-generated")
    later_batch = artifact_batch_id_for(
        COURSE, SESSION, later_run, "later-generated"
    )
    later_content = content(text="Later generated right-cusp revision")
    later_revision = recorded(
        batch_id=later_batch,
        envelope=later_content,
        provenance=generated_provenance(
            later_content,
            run_id=later_run,
            prior=human_revision.revision_id,
        ),
        artifact_id=detail.artifact_id,
        prior=human_revision.revision_id,
        parent_artifact_id=framework.artifact_id,
    )
    later_event = replace(
        proposal_event(
            proposals=(later_revision,),
            key="later-generated",
            run_id=later_run,
        ),
        course_sequence=6,
    )
    with pytest.raises(ValueError, match="parent"):
        apply_event(
            projection,
            replace(
                later_event,
                payload=proposal_event(
                    proposals=(replace(later_revision, parent_artifact_id=None),),
                    key="later-generated",
                    run_id=later_run,
                ).payload,
            ),
            registry(),
        )
    projection = apply_event(projection, later_event, registry())
    revisions = cast(
        JsonObject, cast(JsonObject, projection.state["study_artifacts"])["revisions"]
    )
    later = cast(JsonObject, revisions[str(later_revision.revision_id)])
    assert later["artifact_id"] == str(detail.artifact_id)
    assert later["parent_artifact_id"] == str(framework.artifact_id)


def test_reject_with_supersession_and_wrong_accept_predecessor_are_atomic() -> None:
    projection, _, detail = proposed_pair()
    before = projection.state
    for event in (
        decision_event(
            detail.revision_id,
            ArtifactDecision.REJECT,
            supersedes=ArtifactRevisionStatus.PROPOSED,  # type: ignore[arg-type]
            key="bad-reject",
        ),
        decision_event(
            detail.revision_id,
            ArtifactDecision.ACCEPT,
            supersedes=replace(detail.revision_id, value="wrong"),
            key="bad-accept",
        ),
    ):
        with pytest.raises((TypeError, ValueError)):
            apply_event(projection, event, registry())
        assert projection.state == before


def test_generated_replay_rejects_run_and_origin_mismatch() -> None:
    envelope = content()
    bad = generated_provenance(envelope, run_id=RunId("other-run"))
    batch = artifact_batch_id_for(COURSE, SESSION, RUN, "run-mismatch")
    proposal = recorded(batch_id=batch, envelope=envelope, provenance=bad)
    event = proposal_event(proposals=(proposal,), key="run-mismatch")
    with pytest.raises(ValueError, match="run"):
        apply_event(Projection(COURSE, 1, base_state()), event, registry())
