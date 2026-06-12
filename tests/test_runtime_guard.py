from __future__ import annotations

from policy_index.runtime_guard import assert_policy_project_isolated


def test_runtime_guard_accepts_policy_project():
    status = assert_policy_project_isolated()
    assert "china policy analyse" in status["project_root"]
    assert status["workspace"].endswith("workspace")
