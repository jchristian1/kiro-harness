import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from kiro_worker.db.models import Base
from kiro_worker.db.engine import get_db
from kiro_worker.main import create_app
from kiro_worker.services import project_service, workspace_service, task_service
from kiro_worker.domain.enums import Source, Intent, Operation

TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text("INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1')"))
        conn.commit()
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_client(test_db):
    app = create_app()

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # Patch create_tables to be a no-op (tables already created by test_db fixture)
    import kiro_worker.db.engine as db_engine
    original_create_tables = db_engine.create_tables
    db_engine.create_tables = lambda: None
    with TestClient(app) as client:
        yield client
    db_engine.create_tables = original_create_tables


@pytest.fixture
def sample_project(test_db):
    return project_service.create_project(
        test_db,
        name="test-project",
        source=Source.local_folder,
        source_url="/tmp/test-project",
    )


@pytest.fixture
def sample_workspace(test_db, sample_project):
    import os
    from datetime import datetime, timezone
    from ulid import ULID
    from kiro_worker.db.models import Workspace

    ws_path = "/tmp/test-workspace"
    os.makedirs(ws_path, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    ws = Workspace(
        id=f"ws_{ULID()}",
        project_id=sample_project.id,
        path=ws_path,
        git_remote=None,
        git_branch=None,
        created_at=now,
        last_accessed_at=now,
    )
    test_db.add(ws)
    test_db.commit()
    test_db.refresh(ws)
    project_service.set_workspace(test_db, sample_project, ws.id)
    return ws


@pytest.fixture
def sample_task(test_db, sample_project, sample_workspace):
    return task_service.create_task(
        test_db,
        project_id=sample_project.id,
        workspace_id=sample_workspace.id,
        intent=Intent.add_feature,
        source=Source.local_folder,
        operation=Operation.analyze_then_approve,
        description="Test task description",
    )
