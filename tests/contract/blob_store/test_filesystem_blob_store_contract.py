from __future__ import annotations

from pathlib import Path

from study_agent.adapters.filesystem import FilesystemBlobStore
from study_agent.ports import BlobStore


def exercise_blob_store_contract(store: BlobStore) -> None:
    content = b"immutable source bytes\x00\xff"

    first = store.put(content)
    second = store.put(content)

    assert first == second
    assert first.id.value == f"sha256:{first.checksum_sha256}"
    assert first.byte_length == len(content)
    assert store.get(first) == content


def test_filesystem_store_conforms_to_blob_store_port(tmp_path: Path) -> None:
    exercise_blob_store_contract(FilesystemBlobStore(tmp_path / "blobs"))
