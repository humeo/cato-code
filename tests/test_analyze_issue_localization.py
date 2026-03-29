from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from catocode.runtime_envelope import ActivityResultEnvelope
from catocode.store import Store


@dataclass
class FakeExecResult:
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""

    @property
    def combined(self) -> str:
        if self.stdout and self.stderr:
            return f"{self.stdout}\n[stderr]\n{self.stderr}"
        return self.stdout or self.stderr


class AnalyzeContainerManager:
    def __init__(self, worktree_path: str) -> None:
        self.worktree_path = worktree_path

    def ensure_running(
        self,
        anthropic_api_key: str,
        github_token: str,
        anthropic_base_url: str | None = None,
    ) -> None:
        return None

    def ensure_repo(self, repo_id: str, repo_url: str) -> None:
        return None

    def ensure_session_worktree(self, repo_id: str, repo_url: str, session_id: str) -> str:
        return self.worktree_path

    def reset_checkout(self, workdir: str, target_ref: str | None = None) -> None:
        assert workdir == self.worktree_path

    def exec(self, command: str, workdir: str = "/repos") -> FakeExecResult:
        if command == "test -f CLAUDE.md" and workdir == "/repos/owner-repo":
            return FakeExecResult(exit_code=0)
        if command == "git rev-parse HEAD" and workdir == self.worktree_path:
            return FakeExecResult(stdout="abc123\n")
        raise AssertionError(f"Unexpected command: {command} @ {workdir}")


def _seed_ready_repo(store: Store) -> None:
    store.add_repo("owner-repo", "https://github.com/owner/repo")
    setup_id = store.add_activity("owner-repo", "setup", "watch")
    store.update_activity(setup_id, status="done", summary="ready")
    store.update_repo_lifecycle(
        "owner-repo",
        lifecycle_status="ready",
        last_ready_at="2026-03-24T12:00:00+00:00",
        last_setup_activity_id=setup_id,
    )


@pytest.mark.asyncio
async def test_dispatch_analyze_issue_persists_localization_artifact_for_later_fix(monkeypatch, tmp_path):
    from catocode.dispatcher import _build_activity_envelope, dispatch

    store = Store(db_path=tmp_path / "test.db")
    _seed_ready_repo(store)
    activity_id = store.add_activity("owner-repo", "analyze_issue", "issue:42")
    container_mgr = AnalyzeContainerManager("/repos/.worktrees/owner-repo/runtime-session-1")

    monkeypatch.setattr("catocode.dispatcher._build_prompt", AsyncMock(return_value="analyze prompt"))
    monkeypatch.setattr("catocode.dispatcher._index_repo_from_container", lambda *args, **kwargs: None)
    monkeypatch.setattr("catocode.dispatcher.prepare_codebase_graph_runtime", lambda *args, **kwargs: None)

    async def fake_execute_sdk_runner(**kwargs):
        result = ActivityResultEnvelope(
            status="done",
            summary="Localized issue 42.",
            session={"sdk_session_id": "sdk-analyze", "continued": True},
            writebacks=[],
            artifacts={
                "localization": {
                    "entry_points": ["Query.values"],
                    "explored_paths": [{"entry_point": "Query.values", "status": "sufficient_context"}],
                    "candidate_locations": [
                        {
                            "definition_name": "values",
                            "file_path": "src/query.py",
                            "line_span": [825, 829],
                        }
                    ],
                    "ranked_locations": [
                        {
                            "rank": 1,
                            "file_path": "src/query.py",
                            "line_start": 825,
                            "line_end": 829,
                            "role": "cause",
                            "summary": "values delegates to _values",
                            "why_relevant": "Issue mentions ambiguous status lookup",
                            "symbol_name": "values",
                            "symbol_kind": "function",
                        }
                    ],
                    "finish_reason": "sufficient_context",
                    "search_metrics": {"explored_units": 3},
                }
            },
            metrics={"cost_usd": 0.2, "duration_ms": 500, "turns": 2},
        )
        store.add_log(
            kwargs["activity_id"],
            json.dumps(
                {
                    "type": "result",
                    "result": json.dumps(result.to_dict()),
                    "session_id": "sdk-analyze",
                    "cost_usd": 0.2,
                }
            ),
        )
        return 0, "sdk-analyze", 0.2

    monkeypatch.setattr("catocode.dispatcher._execute_sdk_runner", fake_execute_sdk_runner)

    await dispatch(
        activity_id=activity_id,
        store=store,
        container_mgr=container_mgr,
        anthropic_api_key="sk-ant",
        github_token="ghp-token",
        verbose=False,
    )

    activity = store.get_activity(activity_id)
    assert activity is not None
    metadata = json.loads(activity["metadata"])
    assert metadata["runtime_result"]["artifacts"]["localization"]["ranked_locations"][0]["rank"] == 1

    runtime_session = store.get_runtime_session(activity["session_id"])
    assert runtime_session is not None

    downstream_activity = {
        "id": "fix-activity",
        "repo_id": "owner-repo",
        "kind": "fix_issue",
        "trigger": "issue:42",
        "created_at": "2026-03-29T10:00:00+00:00",
    }
    repo = {"id": "owner-repo", "repo_url": "https://github.com/owner/repo"}
    envelope = _build_activity_envelope(downstream_activity, repo, runtime_session, store, max_turns=200)

    assert envelope.memory["localization"]["ranked_locations"][0]["symbol_name"] == "values"
