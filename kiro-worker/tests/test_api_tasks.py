import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from kiro_worker.adapters.kiro_adapter import KiroInvocationResult
from kiro_worker.domain.enums import TaskStatus
from kiro_worker.services import task_service


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


class TestCreateTask:
    def test_create_task_success(self, test_client: TestClient, sample_project, sample_workspace):
        resp = test_client.post("/tasks", json={
            "project_id": sample_project.id,
            "intent": "add_feature",
            "source": "local_folder",
            "operation": "analyze_then_approve",
            "description": "Add a new feature",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert data["id"].startswith("task_")
        assert data["project_id"] == sample_project.id

    def test_create_task_project_not_found(self, test_client: TestClient):
        resp = test_client.post("/tasks", json={
            "project_id": "nonexistent",
            "intent": "add_feature",
            "source": "local_folder",
            "operation": "analyze_then_approve",
            "description": "Test",
        })
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    def test_create_task_invalid_intent(self, test_client: TestClient, sample_project, sample_workspace):
        resp = test_client.post("/tasks", json={
            "project_id": sample_project.id,
            "intent": "invalid_intent",
            "source": "local_folder",
            "operation": "analyze_then_approve",
            "description": "Test",
        })
        assert resp.status_code == 400

    def test_create_task_missing_description(self, test_client: TestClient, sample_project, sample_workspace):
        resp = test_client.post("/tasks", json={
            "project_id": sample_project.id,
            "intent": "add_feature",
            "source": "local_folder",
            "operation": "analyze_then_approve",
        })
        assert resp.status_code == 400


class TestGetTask:
    def test_get_task_success(self, test_client: TestClient, sample_task):
        resp = test_client.get(f"/tasks/{sample_task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_task.id
        assert data["status"] == "created"
        assert data["last_run"] is None

    def test_get_task_not_found(self, test_client: TestClient):
        resp = test_client.get("/tasks/nonexistent_task_id")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"


class TestApproveTask:
    def test_approve_task_wrong_state(self, test_client: TestClient, sample_task):
        resp = test_client.post(f"/tasks/{sample_task.id}/approve")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATE_FOR_APPROVAL"

    def test_approve_task_success(self, test_client: TestClient, test_db, sample_task, sample_workspace):
        # Move task to awaiting_approval
        task_service.transition_task(test_db, sample_task, TaskStatus.opening)
        task_service.transition_task(test_db, sample_task, TaskStatus.analyzing)
        task_service.transition_task(test_db, sample_task, TaskStatus.awaiting_approval)

        mock_result = KiroInvocationResult(
            exit_code=0,
            stdout=json.dumps(VALID_IMPLEMENTATION_OUTPUT),
            stderr="",
            parsed_output=VALID_IMPLEMENTATION_OUTPUT,
            parse_status="ok",
            failure_reason=None,
        )
        with patch("kiro_worker.routes.tasks.invoke_kiro", new=AsyncMock(return_value=mock_result)):
            resp = test_client.post(f"/tasks/{sample_task.id}/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_at"] is not None

    def test_approve_task_not_found(self, test_client: TestClient):
        resp = test_client.post("/tasks/nonexistent/approve")
        assert resp.status_code == 404


class TestReviseTask:
    def test_revise_task_wrong_state(self, test_client: TestClient, sample_task):
        resp = test_client.post(f"/tasks/{sample_task.id}/revise", json={"instructions": "Fix it"})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    def test_revise_task_success(self, test_client: TestClient, test_db, sample_task, sample_workspace):
        # Move task to awaiting_revision
        task_service.transition_task(test_db, sample_task, TaskStatus.opening)
        task_service.transition_task(test_db, sample_task, TaskStatus.analyzing)
        task_service.transition_task(test_db, sample_task, TaskStatus.awaiting_approval)
        task_service.transition_task(test_db, sample_task, TaskStatus.implementing)
        task_service.transition_task(test_db, sample_task, TaskStatus.validating)
        task_service.transition_task(test_db, sample_task, TaskStatus.awaiting_revision)

        mock_result = KiroInvocationResult(
            exit_code=0,
            stdout=json.dumps(VALID_IMPLEMENTATION_OUTPUT),
            stderr="",
            parsed_output=VALID_IMPLEMENTATION_OUTPUT,
            parse_status="ok",
            failure_reason=None,
        )
        with patch("kiro_worker.routes.tasks.invoke_kiro", new=AsyncMock(return_value=mock_result)):
            resp = test_client.post(f"/tasks/{sample_task.id}/revise", json={"instructions": "Fix the bug"})
        assert resp.status_code == 200

    def test_revise_task_missing_instructions(self, test_client: TestClient, test_db, sample_task):
        task_service.transition_task(test_db, sample_task, TaskStatus.opening)
        task_service.transition_task(test_db, sample_task, TaskStatus.analyzing)
        task_service.transition_task(test_db, sample_task, TaskStatus.awaiting_approval)
        task_service.transition_task(test_db, sample_task, TaskStatus.implementing)
        task_service.transition_task(test_db, sample_task, TaskStatus.validating)
        task_service.transition_task(test_db, sample_task, TaskStatus.awaiting_revision)

        resp = test_client.post(f"/tasks/{sample_task.id}/revise", json={})
        assert resp.status_code == 400
