from __future__ import annotations

import json
from typing import Any

import duckdb
import polars as pl

from policy_index.io import write_json
from policy_index.paths import EXPORTS_DIR, WORKSPACE_DIR, ensure_runtime_dirs

from .models import SupportObservation
from .validation import observations_to_frame


class SSIStorage:
    def __init__(self) -> None:
        ensure_runtime_dirs()
        self.db_path = WORKSPACE_DIR / "index" / "ssi_engine.duckdb"
        self.observations_jsonl = WORKSPACE_DIR / "observations" / "support_observations.jsonl"
        self.snapshot_path = WORKSPACE_DIR / "index" / "state_support_index_latest.json"

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path))

    def save_observations(self, observations: list[SupportObservation]) -> None:
        frame = observations_to_frame(observations)
        frame_for_duckdb = frame.with_columns(
            pl.col("source_document_ids").map_elements(
                lambda value: json.dumps(value.to_list() if hasattr(value, "to_list") else value, ensure_ascii=False),
                return_dtype=pl.String,
            )
        )
        self.observations_jsonl.parent.mkdir(parents=True, exist_ok=True)
        self.observations_jsonl.write_text(
            "\n".join(json.dumps(item.to_record(), ensure_ascii=False) for item in observations) + "\n",
            encoding="utf-8",
        )
        with self._connect() as con:
            con.register("support_observations_df", frame_for_duckdb)
            con.execute("CREATE OR REPLACE TABLE support_observations AS SELECT * FROM support_observations_df")

    def load_observations(self) -> list[dict[str, Any]]:
        if not self.observations_jsonl.exists():
            return []
        return [
            json.loads(line)
            for line in self.observations_jsonl.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def save_snapshot(self, snapshot: dict[str, Any]) -> None:
        write_json(self.snapshot_path, snapshot)
        write_json(EXPORTS_DIR / "state_support_index_snapshot.json", snapshot)
        write_json(EXPORTS_DIR / "methodology.json", snapshot.get("methodology", {}))

        observations = snapshot.get("observation_results", [])
        (EXPORTS_DIR / "support_observations.jsonl").write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in observations) + ("\n" if observations else ""),
            encoding="utf-8",
        )
        with self._connect() as con:
            for table_name, rows in {
                "ssi_observation_results": snapshot.get("observation_results", []),
                "ssi_industry_values": snapshot.get("industry_values", []),
                "ssi_china_values": snapshot.get("china_values", []),
                "ssi_channel_breakdowns": snapshot.get("channel_breakdowns", []),
            }.items():
                frame = pl.DataFrame(rows) if rows else pl.DataFrame()
                con.register(f"{table_name}_df", frame)
                con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM {table_name}_df")

    def load_snapshot(self) -> dict[str, Any]:
        if not self.snapshot_path.exists():
            return {}
        return json.loads(self.snapshot_path.read_text(encoding="utf-8"))
