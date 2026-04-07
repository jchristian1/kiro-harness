from pydantic import BaseModel
from typing import Optional
from kiro_worker.domain.enums import Intent, Source, Operation
from kiro_worker.schemas.run import RunSummary


class TaskCreate(BaseModel):
    project_id: str
    intent: Intent
    source: Source
    operation: Operation
    description: str


class TaskResponse(BaseModel):
    id: str
    project_id: str
    workspace_id: str
    intent: str
    source: str
    operation: str
    description: str
    status: str
    approved_at: Optional[str]
    created_at: str
    updated_at: str
    last_run: Optional[RunSummary] = None


class ReviseRequest(BaseModel):
    instructions: str
