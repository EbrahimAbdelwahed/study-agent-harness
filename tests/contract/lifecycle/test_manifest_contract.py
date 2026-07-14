from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from study_agent.lifecycle import (
    LifecycleManifestV1,
    ManifestValidationError,
)

FIXTURE = (
    Path(__file__).parents[3]
    / "specs"
    / "done"
    / "agent-managed-lifecycle"
    / "fixtures"
    / "manifest-v1.json"
)
GOLDEN_CANONICAL_LENGTH = 417
GOLDEN_FINGERPRINT = "bdcc1337312ed868c4db1859fdcfe3a7ee4093ba96539e38421bdb69bf30f1d7"


def _minimal_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "repository": {"path": "repo", "model": None},
        "courses": [],
    }


def _course(course_id: str = "course") -> dict[str, Any]:
    return {
        "course_id": course_id,
        "title": "Title",
        "language": "en",
        "exam_date": None,
        "learning_goals": ["Goal"],
        "assessment_styles": [],
        "sources": [],
    }


def _source(source_id: str = "source") -> dict[str, Any]:
    return {
        "source_id": source_id,
        "path": f"materials/{source_id}.md",
        "title": None,
        "trust_level": 0,
        "source_role": "material",
    }


def _parse(value: object) -> LifecycleManifestV1:
    return LifecycleManifestV1.from_bytes(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    )


def test_golden_canonical_bytes_and_domain_separated_fingerprint_are_pinned() -> None:
    manifest = LifecycleManifestV1.from_bytes(FIXTURE.read_bytes())

    assert len(manifest.canonical_bytes()) == GOLDEN_CANONICAL_LENGTH
    assert manifest.fingerprint == GOLDEN_FINGERPRINT
    assert manifest.canonical_bytes().decode() == (
        '{"courses":[{"assessment_styles":[],"course_id":"anatomy-example",'
        '"exam_date":null,"language":"en","learning_goals":['
        '"Explain the supplied source material"],"sources":[{"path":'
        '"materials/anatomy-notes.md","source_id":"anatomy-notes",'
        '"source_role":"course_material","title":"Anatomy notes",'
        '"trust_level":80}],"title":"Anatomy example"}],"repository":'
        '{"model":null,"path":"runtime/study-repository"},"schema_version":1}'
    )


def test_reordered_input_has_identical_bytes_and_ids_sort_without_reordering_intent() -> None:
    value = _minimal_manifest()
    second = _course("course-b")
    second["learning_goals"] = ["Goal B2", "Goal B1"]
    second["assessment_styles"] = ["oral", "written"]
    second["sources"] = [_source("source-b"), _source("source-a")]
    first = _course("course-a")
    value["courses"] = [second, first]

    reordered = {
        "courses": [
            {key: item for key, item in reversed(tuple(second.items()))},
            {key: item for key, item in reversed(tuple(first.items()))},
        ],
        "repository": {"model": None, "path": "repo"},
        "schema_version": 1,
    }
    left = _parse(value)
    right = _parse(reordered)

    assert left.canonical_bytes() == right.canonical_bytes()
    assert left.fingerprint == right.fingerprint
    assert [course.course_id for course in left.courses] == ["course-a", "course-b"]
    assert [source.source_id for source in left.courses[1].sources] == [
        "source-a",
        "source-b",
    ]
    assert left.courses[1].learning_goals == ("Goal B2", "Goal B1")
    assert left.courses[1].assessment_styles == ("oral", "written")


def test_manifest_values_are_deeply_immutable_and_detached_from_input() -> None:
    value = _minimal_manifest()
    course = _course()
    course["sources"] = [_source()]
    value["courses"] = [course]
    value["repository"] = {
        "path": "repo",
        "model": {
            "adapter_id": "generic",
            "credential_env": None,
            "settings": {"nested": {"modes": ["fast"]}},
        },
    }
    manifest = _parse(value)
    cast_model = manifest.repository.model
    assert cast_model is not None

    value["courses"].clear()
    value["repository"]["model"]["settings"]["nested"]["modes"].append("changed")
    assert manifest.courses[0].sources[0].source_id == "source"
    assert cast_model.settings["nested"] == {"modes": ("fast",)}
    with pytest.raises(FrozenInstanceError):
        manifest.schema_version = 2  # type: ignore[misc]
    with pytest.raises(TypeError):
        cast_model.settings["new"] = "value"  # type: ignore[index]


@pytest.mark.parametrize(
    ("field", "maximum"),
    [
        ("course_id", 256),
        ("language", 256),
        ("title", 1024),
    ],
)
def test_course_string_bounds_accept_maximum_and_reject_bound_plus_one(
    field: str, maximum: int
) -> None:
    value = _minimal_manifest()
    course = _course()
    course[field] = "x" * maximum
    value["courses"] = [course]
    _parse(value)

    course[field] += "x"
    with pytest.raises(ManifestValidationError):
        _parse(value)


@pytest.mark.parametrize(
    ("field", "maximum"),
    [("source_id", 256), ("source_role", 256), ("title", 1024)],
)
def test_source_string_bounds_accept_maximum_and_reject_bound_plus_one(
    field: str, maximum: int
) -> None:
    value = _minimal_manifest()
    course = _course()
    source = _source()
    source[field] = "x" * maximum
    if field == "source_id":
        source["path"] = "source.md"
    course["sources"] = [source]
    value["courses"] = [course]
    _parse(value)

    source[field] += "x"
    with pytest.raises(ManifestValidationError):
        _parse(value)


@pytest.mark.parametrize("path_field", ["repository", "source"])
def test_path_bounds_accept_256_and_reject_257_code_points(path_field: str) -> None:
    value = _minimal_manifest()
    if path_field == "repository":
        value["repository"]["path"] = "r" * 256
    else:
        course = _course()
        source = _source()
        source["path"] = "p" * 253 + ".md"
        course["sources"] = [source]
        value["courses"] = [course]
    _parse(value)

    if path_field == "repository":
        value["repository"]["path"] += "r"
    else:
        value["courses"][0]["sources"][0]["path"] = "p" * 254 + ".md"
    with pytest.raises(ManifestValidationError):
        _parse(value)


@pytest.mark.parametrize(
    ("field", "minimum", "maximum", "item_maximum"),
    [
        ("learning_goals", 1, 64, 2048),
        ("assessment_styles", 0, 32, 512),
    ],
)
def test_ordered_text_collection_count_and_item_bounds(
    field: str, minimum: int, maximum: int, item_maximum: int
) -> None:
    value = _minimal_manifest()
    course = _course()
    course[field] = ["x"] * minimum
    value["courses"] = [course]
    _parse(value)

    course[field] = ["x" * item_maximum]
    _parse(value)
    course[field][0] += "x"
    with pytest.raises(ManifestValidationError):
        _parse(value)
    course[field] = ["x"] * maximum
    _parse(value)
    course[field] = ["x"] * (maximum + 1)
    with pytest.raises(ManifestValidationError):
        _parse(value)


def test_course_and_source_count_bounds_include_zero_maximum_and_bound_plus_one() -> None:
    _parse(_minimal_manifest())
    value = _minimal_manifest()
    value["courses"] = [_course(f"course-{index:03}") for index in range(128)]
    _parse(value)
    value["courses"].append(_course("overflow"))
    with pytest.raises(ManifestValidationError):
        _parse(value)

    value = _minimal_manifest()
    course = _course()
    course["sources"] = [_source(f"source-{index:04}") for index in range(1024)]
    value["courses"] = [course]
    _parse(value)
    course["sources"].append(_source("overflow"))
    with pytest.raises(ManifestValidationError):
        _parse(value)


def test_total_source_bound_accepts_4096_and_rejects_4097() -> None:
    value = _minimal_manifest()
    courses = []
    for course_index in range(4):
        course = _course(f"course-{course_index}")
        course["sources"] = [
            _source(f"s{course_index}-{source_index}") for source_index in range(1024)
        ]
        courses.append(course)
    value["courses"] = courses
    _parse(value)

    extra = _course("extra")
    extra["sources"] = [_source("extra")]
    courses.append(extra)
    with pytest.raises(ManifestValidationError):
        _parse(value)


@pytest.mark.parametrize("trust", [0, 100])
def test_trust_level_accepts_closed_numeric_bounds(trust: int) -> None:
    value = _minimal_manifest()
    course = _course()
    source = _source()
    source["trust_level"] = trust
    course["sources"] = [source]
    value["courses"] = [course]
    assert _parse(value).courses[0].sources[0].trust_level == trust


@pytest.mark.parametrize("trust", [-1, 101, True, 1.0, "1"])
def test_trust_level_rejects_out_of_range_and_non_integer_values(trust: object) -> None:
    value = _minimal_manifest()
    course = _course()
    source = _source()
    source["trust_level"] = trust
    course["sources"] = [source]
    value["courses"] = [course]
    with pytest.raises(ManifestValidationError):
        _parse(value)


@pytest.mark.parametrize(
    "exam_date", ["2025-02-29", "2026-2-01", "2026-01-1", "2026-13-01", True]
)
def test_exam_date_requires_a_real_zero_padded_iso_date(exam_date: object) -> None:
    value = _minimal_manifest()
    course = _course()
    course["exam_date"] = exam_date
    value["courses"] = [course]
    with pytest.raises(ManifestValidationError):
        _parse(value)


@pytest.mark.parametrize(
    "path",
    ["", ".", "..", "/absolute", "\\server", "C:/drive", "a/../b", "a/./b", "a//b", "a\\b"],
)
def test_repository_path_rejects_blank_absolute_dot_and_lexical_traversal(path: str) -> None:
    value = _minimal_manifest()
    value["repository"]["path"] = path
    with pytest.raises(ManifestValidationError):
        _parse(value)


@pytest.mark.parametrize("path", ["notes.pdf", "notes.md/child", "../notes.md", "/notes.md"])
def test_source_path_requires_safe_explicit_text_or_markdown_file(path: str) -> None:
    value = _minimal_manifest()
    course = _course()
    source = _source()
    source["path"] = path
    course["sources"] = [source]
    value["courses"] = [course]
    with pytest.raises(ManifestValidationError):
        _parse(value)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(extra=None),
        lambda value: value.pop("courses"),
        lambda value: value["repository"].update(extra=None),
        lambda value: value["repository"].pop("model"),
        lambda value: value["repository"].update(
            model={
                "adapter_id": "a",
                "credential_env": None,
                "settings": {},
                "extra": None,
            }
        ),
        lambda value: value["courses"][0].update(extra=None),
        lambda value: value["courses"][0].pop("sources"),
        lambda value: value["courses"][0]["sources"][0].update(extra=None),
        lambda value: value["courses"][0]["sources"][0].pop("title"),
    ],
)
def test_every_object_level_is_closed_and_has_no_implicit_defaults(mutate: Any) -> None:
    value = _minimal_manifest()
    course = _course()
    course["sources"] = [_source()]
    value["courses"] = [course]
    mutate(value)
    with pytest.raises(ManifestValidationError):
        _parse(value)


def test_duplicate_json_keys_and_duplicate_explicit_ids_are_rejected() -> None:
    with pytest.raises(ManifestValidationError):
        LifecycleManifestV1.from_bytes(
            b'{"schema_version":1,"schema_version":1,"repository":{},"courses":[]}'
        )

    value = _minimal_manifest()
    value["courses"] = [_course("same"), _course("same")]
    with pytest.raises(ManifestValidationError):
        _parse(value)
    course = _course()
    course["sources"] = [_source("same"), _source("same")]
    value["courses"] = [course]
    with pytest.raises(ManifestValidationError):
        _parse(value)


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff",
        b'{"schema_version":true,"repository":{"path":"repo","model":null},"courses":[]}',
        b'{"schema_version":1,"repository":{"path":"repo","model":null},"courses":[],"x":NaN}',
        b'{"schema_version":1,"repository":{"path":"repo","model":{"adapter_id":"a","credential_env":null,"settings":{"n":Infinity}}},"courses":[]}',
    ],
)
def test_invalid_utf8_bool_as_int_and_non_finite_numbers_are_rejected(payload: bytes) -> None:
    with pytest.raises(ManifestValidationError):
        LifecycleManifestV1.from_bytes(payload)


def test_manifest_byte_bound_accepts_one_mib_or_less_and_rejects_bound_plus_one() -> None:
    # Whitespace is valid JSON padding and exercises the input-byte bound independently.
    base = json.dumps(_minimal_manifest(), separators=(",", ":")).encode()
    maximum = base + b" " * (1024 * 1024 - len(base))
    LifecycleManifestV1.from_bytes(maximum)
    with pytest.raises(ManifestValidationError):
        LifecycleManifestV1.from_bytes(maximum + b" ")


def _manifest_with_settings(settings: object) -> dict[str, Any]:
    value = _minimal_manifest()
    value["repository"]["model"] = {
        "adapter_id": "a",
        "credential_env": None,
        "settings": settings,
    }
    return value


def test_settings_key_string_and_container_width_bounds() -> None:
    _parse(_manifest_with_settings({"k" * 128: "v" * 4096}))
    for settings in ({"k" * 129: "v"}, {"k": "v" * 4097}):
        with pytest.raises(ManifestValidationError):
            _parse(_manifest_with_settings(settings))

    _parse(_manifest_with_settings({f"k{index}": None for index in range(256)}))
    with pytest.raises(ManifestValidationError):
        _parse(_manifest_with_settings({f"k{index}": None for index in range(257)}))
    _parse(_manifest_with_settings({"items": [None] * 256}))
    with pytest.raises(ManifestValidationError):
        _parse(_manifest_with_settings({"items": [None] * 257}))


def test_settings_depth_and_node_bounds_are_iterative_and_exact() -> None:
    nested: object = "leaf"
    for index in range(15):
        nested = {f"level_{index}": nested}
    _parse(_manifest_with_settings(nested))
    nested = {"overflow": nested}
    with pytest.raises(ManifestValidationError):
        _parse(_manifest_with_settings(nested))

    exact_nodes = {"rows": [[None] * size for size in (255, 255, 254, 254)]}
    _parse(_manifest_with_settings(exact_nodes))
    excessive_nodes = {"rows": [[None] * size for size in (255, 255, 255, 254)]}
    with pytest.raises(ManifestValidationError):
        _parse(_manifest_with_settings(excessive_nodes))


def test_recursive_or_parser_deep_settings_fail_as_one_safe_validation_error() -> None:
    # Insert an object whose decoder nesting exceeds Python's recursion guard.
    nested = b'{"x":' * 1100 + b"null" + b"}" * 1100
    payload = (
        b'{"schema_version":1,"repository":{"path":"repo","model":'
        b'{"adapter_id":"adapter","credential_env":null,"settings":'
        + nested
        + b'}},"courses":[]}'
    )
    with pytest.raises(ManifestValidationError) as captured:
        LifecycleManifestV1.from_bytes(payload)
    assert "adapter" not in str(captured.value)


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "api_key",
        "accessToken",
        "client-secret",
        "authority",
        "capabilities",
        "principal_id",
        "idempotency_key",
        "skill",
        "playbooks",
        "prompt_template",
        "tool",
        "plugin",
        "command",
        "exec",
        "executable",
        "imports",
        "glob",
        "include",
        "delete",
        "deletion",
        "remove",
        "removal",
        "script",
        "hook",
        "functions",
        "function_call",
        "system",
        "instructions",
    ],
)
def test_settings_cannot_select_secrets_behavior_authority_or_executable_content(
    forbidden_key: str,
) -> None:
    secret = "do-not-echo-secret-value"
    with pytest.raises(ManifestValidationError) as captured:
        _parse(_manifest_with_settings({forbidden_key: secret}))
    assert secret not in str(captured.value)


def test_model_adapter_and_repository_config_serialization_bound_is_enforced() -> None:
    _parse(_manifest_with_settings({"payload": "x" * 4096}))
    settings = {f"setting_{index:03}": "x" * 4096 for index in range(16)}
    with pytest.raises(ManifestValidationError, match="configuration is invalid"):
        _parse(_manifest_with_settings(settings))


def test_model_adapter_id_bound_and_credential_environment_contract() -> None:
    value = _manifest_with_settings({})
    model = value["repository"]["model"]
    model["adapter_id"] = "a" * 256
    model["credential_env"] = "STUDY_AGENT_MODEL_KEY"
    _parse(value)

    model["adapter_id"] += "a"
    with pytest.raises(ManifestValidationError):
        _parse(value)
    model["adapter_id"] = "adapter"
    model["credential_env"] = "literal-secret-value"
    with pytest.raises(ManifestValidationError):
        _parse(value)


@pytest.mark.parametrize(
    "path",
    [
        "mailto:repo",
        "CON",
        "nested/PRN.txt",
        "nested/trailing. ",
        "nested/trailing.",
    ],
)
def test_repository_paths_reject_non_portable_components(path: str) -> None:
    value = _minimal_manifest()
    value["repository"]["path"] = path
    with pytest.raises(ManifestValidationError):
        _parse(value)


@pytest.mark.parametrize("control", ["\x1b", "\x7f", "\u202e"])
def test_text_fields_reject_terminal_and_format_controls(control: str) -> None:
    value = _minimal_manifest()
    course = _course(f"course{control}id")
    value["courses"] = [course]
    with pytest.raises(ManifestValidationError):
        _parse(value)


def test_escaped_unpaired_surrogate_is_rejected_before_canonicalization() -> None:
    value = _minimal_manifest()
    value["courses"] = [_course("course\ud800id")]
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()
    with pytest.raises(ManifestValidationError):
        LifecycleManifestV1.from_bytes(payload)
