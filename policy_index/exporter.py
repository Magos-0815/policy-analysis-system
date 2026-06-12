from __future__ import annotations

from .io import write_json
from .paths import EXPORTS_DIR
from .repository import PolicyRepository
from .ssi_engine.storage import SSIStorage


class SnapshotExporter:
    def __init__(self, repository: PolicyRepository | None = None) -> None:
        self.repository = repository or PolicyRepository()
        self.ssi_storage = SSIStorage()

    def export_latest(self) -> dict[str, str]:
        snapshot = self.repository.load_index_snapshot()
        output = EXPORTS_DIR / "policy_index_snapshot.json"
        write_json(output, snapshot)
        result = {"policy_index_snapshot": str(output)}
        ssi_snapshot = self.ssi_storage.load_snapshot()
        if ssi_snapshot:
            ssi_output = EXPORTS_DIR / "state_support_index_snapshot.json"
            write_json(ssi_output, ssi_snapshot)
            result["state_support_index_snapshot"] = str(ssi_output)
        return result
