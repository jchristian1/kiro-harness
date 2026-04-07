import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from kiro_worker.adapters.kiro_adapter import KiroInvocationResult
from kiro_worker.domain.enums import TaskStatus
from kiro_worker.services import task_service, run_service


VALID_ANALYSIS_OUTPUT = {
    "schema_version": "1",
    "mode": "analyze",
    "headline": "Test analysis",
    "findings": ["finding 1"],
    "affected_areas": ["src/main.py"],
    "tradeoffs": [],
    "risks": [],
    "implementation_steps": ["step 1"],
    "validation_commands": [],
    "questions": [],
    "recommended_next_step": "approve_and_implement",
}

VALID_IMPLEMENTATION_OUTPUT = {
    "schema_version": "1",
    "mode": "implement",
    "headline": "Test implementation",
    "files_changed": [{"path": "src/main.py", "action": "modified", "description": "Updated"}],
    "changes_summary": "Made changes",
    "validation_run": None,
    "known_issues": [],
    "follow_ups": [],
    "recommended_next_step": "run_validation",
}

VALID_VALIDATION_OUTPUT = {
    "schema_version": "1",
    "mode": "validate",
    "commands_run": ["npm test"],
    "results": [{"command": "npm test", "exit_code": 0, "passed": True, "output_excerpt": "all pass"}],
    "passed": True,
    "issues_found": [],
    "recommended_next_step": "mark_done",
}


class TestTriggerRun:
    def test_trigger_run_success_analyze(self, test_client: TestClient, sample_task):
        mock_result = KiroInvocationResult(
            exit_code=0,
            stdout=json.dumps(VALID_ANALYSIS_OUTPUT),
            stderr="",
            parsed_output=VALID_ANALYSIS_OUTPUT,
            parse_status="ok",
            failure_reason=None,
        )
        with patch("kiro_worker.routes.tasks.invoke_kiro", new=AsyncMock(return_value=mock_result)):
            resp = test_client.post(f"/tasks/{sample_task.id}/runs", json={"mode": "analyze"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["mode"] == "analyze"
        assert data["id"].startswith("run_")

    def test_trigger_run_approval_required(self, test_client: TestClient, test_db, sample_task):
        task_service.transition_task(test_db, sample_task, TaskStatus.opening)
        task_service.transition_task(test_db, sample_task, TaskStatus.analyzing)
        task_service.transition_task(test_db, sample_task, TaskStatus.awaiting_approval)

        resp = test_client.post(f"/tasks/{sample_task.id}/runs", json={"mode": "implement"})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "APPROVAL_REQUIRED"

    def test_trigger_run_invalid_state(self, test_client: TestClient, test_db, sample_task):
        task_service.transition_task(test_db, sample_task, TaskStatus.opening)
        task_service.transition_task(test_db, sample_task, TaskStatus.analyzing)

        resp = test_client.post(f"/tasks/{sample_task.id}/runs", json={"mode": "analyze"})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    def test_trigger_run_task_not_found(self, test_client: TestClient):
        resp = test_client.post("/tasks/nonexistent/runs", json={"mode": "analyze"})
        assert resp.status_code == 404


class TestListRuns:
    def test_list_runs_success(self, test_client: TestClient, test_db, sample_task, sample_workspace):
        mock_result = KiroInvocationResult(
            exit_code=0,
            stdout=json.dumps(VALID_ANALYSIS_OUTPUT),
            stderr="",
            parsed_output=VALID_ANALYSIS_OUTPUT,
            parse_status="ok",
            failure_reason=None,
        )
        with patch("kiro_worker.routes.tasks.invoke_kiro", new=AsyncMock(return_value=mock_result)):
            test_client.post(f"/tasks/{sample_task.id}/runs", json={"mode": "analyze"})

        resp = test_client.get(f"/tasks/{sample_task.id}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert len(data["runs"]) >= 1

    def test_list_runs_task_not_found(self, test_client: TestClient):
        resp = test_client.get("/tasks/nonexistent/runs")
        assert resp.status_code == 404


class TestGetRun:
    def test_get_run_success(self, test_client: TestClient, test_db, sample_task, sample_workspace):
        mock_result = KiroInvocationResult(
            exit_code=0,
            stdout=json.dumps(VALID_ANALYSIS_OUTPUT),
            stderr="",
            parsed_output=VALID_ANALYSIS_OUTPUT,
            parse_status="ok",
            failure_reason=None,
        )
        with patch("kiro_worker.routes.tasks.invoke_kiro", new=AsyncMock(return_value=mock_result)):
            run_resp = test_client.post(f"/tasks/{sample_task.id}/runs", json={"mode": "analyze"})
        run_id = run_resp.json()["id"]

        resp = test_client.get(f"/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == run_id
        assert data["mode"] == "analyze"
        assert isinstance(data["context_snapshot"], dict)

    def test_get_run_not_found(self, test_client: TestClient):
        resp = test_client.get("/runs/nonexistent_run")
        assert resp.status_code == 404


class TestGetArtifact:
    def test_get_artifact_success(self, test_client: TestClient, test_db, sample_task, sample_workspace):
        mock_result = KiroInvocationResult(
            exit_code=0,
            stdout=json.dumps(VALID_ANALYSIS_OUTPUT),
            stderr="",
            parsed_output=VALID_ANALYSIS_OUTPUT,
            parse_status="ok",
            failure_reason=None,
        )
        with patch("kiro_worker.routes.tasks.invoke_kiro", new=AsyncMock(return_value=mock_result)):
            run_resp = test_client.post(f"/tasks/{sample_task.id}/runs", json={"mode": "analyze"})
        run_id = run_resp.json()["id"]

        resp = test_client.get(f"/runs/{run_id}/artifact")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "analysis"
        assert data["run_id"] == run_id
        assert isinstance(data["content"], dict)

    def test_get_artifact_not_found(self, test_client: TestClient, test_db, sample_task, sample_workspace):
        # Create a run that fails (no artifact)
        mock_result = KiroInvocationResult(
            exit_code=1,
            stdout="",
            stderr="error",
            parsed_output=None,
            parse_status="parse_failed",
            failure_reason="exit_code:1: error",
        )
        with patch("kiro_worker.routes.tasks.invoke_kiro", new=AsyncMock(return_value=mock_result)):
            run_resp = test_client.post(f"/tasks/{sample_task.id}/runs", json={"mode": "analyze"})
        run_id = run_resp.json()["id"]

        resp = test_client.get(f"/runs/{run_id}/artifact")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "ARTIFACT_NOT_FOUND"
