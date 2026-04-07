import os
import pytest
from fastapi.testclient import TestClient


class TestCreateProject:
    def test_create_project_success(self, test_client: TestClient):
        resp = test_client.post("/projects", json={
            "name": "my-project",
            "source": "local_folder",
            "source_url": "/tmp/my-project",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "my-project"
        assert data["source"] == "local_folder"
        assert data["id"].startswith("proj_")
        assert data["workspace_id"] is None

    def test_create_project_new_project_no_url(self, test_client: TestClient):
        resp = test_client.post("/projects", json={
            "name": "brand-new",
            "source": "new_project",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_url"] is None

    def test_create_project_duplicate_name_conflict(self, test_client: TestClient):
        test_client.post("/projects", json={"name": "dup-project", "source": "new_project"})
        resp = test_client.post("/projects", json={"name": "dup-project", "source": "new_project"})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "PROJECT_NAME_CONFLICT"

    def test_create_project_missing_name(self, test_client: TestClient):
        resp = test_client.post("/projects", json={"source": "new_project"})
        assert resp.status_code == 400

    def test_create_project_missing_source_url_for_github(self, test_client: TestClient):
        resp = test_client.post("/projects", json={
            "name": "github-project",
            "source": "github_repo",
        })
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_create_project_invalid_source(self, test_client: TestClient):
        resp = test_client.post("/projects", json={
            "name": "bad-source",
            "source": "invalid_source",
        })
        assert resp.status_code == 400


class TestOpenWorkspace:
    def test_open_workspace_project_not_found(self, test_client: TestClient):
        resp = test_client.post("/projects/nonexistent_id/workspaces", json={})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    def test_open_workspace_already_exists(self, test_client: TestClient, sample_project, sample_workspace):
        resp = test_client.post(f"/projects/{sample_project.id}/workspaces", json={})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "WORKSPACE_ALREADY_EXISTS"

    def test_open_workspace_new_project_success(self, test_client: TestClient, tmp_path):
        # Create a project with new_project source
        resp = test_client.post("/projects", json={
            "name": "new-ws-project",
            "source": "new_project",
        })
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        # Override safe root to tmp_path
        import kiro_worker.routes.projects as proj_routes
        import kiro_worker.services.workspace_service as ws_svc
        original = ws_svc.open_workspace

        async def mock_open(db, project, safe_root, git_branch=None):
            from datetime import datetime, timezone
            from ulid import ULID
            from kiro_worker.db.models import Workspace
            ws_path = str(tmp_path / project.name)
            os.makedirs(ws_path, exist_ok=True)
            now = datetime.now(timezone.utc).isoformat()
            ws = Workspace(
                id=f"ws_{ULID()}",
                project_id=project.id,
                path=ws_path,
                git_remote=None,
                git_branch=None,
                created_at=now,
                last_accessed_at=now,
            )
            db.add(ws)
            db.commit()
            db.refresh(ws)
            return ws

        ws_svc.open_workspace = mock_open
        try:
            resp2 = test_client.post(f"/projects/{project_id}/workspaces", json={})
            assert resp2.status_code == 201
            data = resp2.json()
            assert data["project_id"] == project_id
        finally:
            ws_svc.open_workspace = original


class TestGetActiveTask:
    def test_get_active_task_success(self, test_client: TestClient, sample_project, sample_task):
        resp = test_client.get(f"/projects/{sample_project.id}/active-task")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_task.id
        assert data["status"] == "created"

    def test_get_active_task_no_active_task(self, test_client: TestClient, sample_project):
        resp = test_client.get(f"/projects/{sample_project.id}/active-task")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NO_ACTIVE_TASK"

    def test_get_active_task_project_not_found(self, test_client: TestClient):
        resp = test_client.get("/projects/nonexistent/active-task")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"
