from __future__ import annotations

from typing import Any

from .io import read_json, read_jsonl, write_json
from .paths import WORKSPACE_DIR, ensure_runtime_dirs


class PolicyRepository:
    def __init__(self) -> None:
        ensure_runtime_dirs()

    def document_path(self, document_id: str):
        return WORKSPACE_DIR / "documents" / f"{document_id}.json"

    def raw_path(self, source_id: str, document_id: str):
        return WORKSPACE_DIR / "raw" / source_id / f"{document_id}.html"

    def text_path(self, document_id: str):
        return WORKSPACE_DIR / "text" / f"{document_id}.txt"

    def save_document(self, document: dict[str, Any], raw: str, text: str) -> dict[str, Any]:
        source_id = document["source_id"]
        document_id = document["document_id"]
        raw_path = self.raw_path(source_id, document_id)
        text_path = self.text_path(document_id)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw, encoding="utf-8")
        text_path.write_text(text, encoding="utf-8")
        document = {
            **document,
            "raw_path": str(raw_path),
            "text_path": str(text_path),
        }
        write_json(self.document_path(document_id), document)
        return document

    def list_documents(self) -> list[dict[str, Any]]:
        docs_dir = WORKSPACE_DIR / "documents"
        if not docs_dir.exists():
            return []
        return [read_json(path) for path in sorted(docs_dir.glob("*.json"))]

    def save_classification(self, document_id: str, classification: dict[str, Any]) -> None:
        write_json(WORKSPACE_DIR / "observations" / "classifications" / f"{document_id}.json", classification)

    def list_classifications(self) -> list[dict[str, Any]]:
        base = WORKSPACE_DIR / "observations" / "classifications"
        if not base.exists():
            return []
        return [read_json(path) for path in sorted(base.glob("*.json"))]

    def save_index_snapshot(self, snapshot: dict[str, Any]) -> None:
        write_json(WORKSPACE_DIR / "index" / "policy_signal_latest.json", snapshot)

    def load_index_snapshot(self) -> dict[str, Any]:
        return read_json(WORKSPACE_DIR / "index" / "policy_signal_latest.json", {})

    def list_events(self) -> list[dict[str, Any]]:
        return read_jsonl(WORKSPACE_DIR / "events" / "events.jsonl")
