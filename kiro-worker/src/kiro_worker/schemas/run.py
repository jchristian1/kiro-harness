from pydantic import BaseModel
from typing import Optional, Any
from kiro_worker.domain.enums import RunMode


class RunCreate(BaseModel):
    mode: RunMode


class RunSummary(BaseModel):
    id: str
    mode: str
    status: str
    started_at: str
    completed_at: Optional[str]
    failure_reason: Optional[str]
    progress_message: Optional[str] = None
    last_activity_at: Optional[str] = None


class RunListItem(BaseModel):
    id: str
    task_id: str
    mode: str
    status: str
    agent: str
    skill: str
    parse_status: Optional[str]
    failure_reason: Optional[str]
    started_at: str
    completed_at: Optional[str]


class RunResponse(BaseModel):
    id: str
    task_id: str
    mode: str
    status: str
    agent: str
    skill: str
    context_snapshot: Any
    raw_output: Optional[str]
    parse_status: Optional[str]
    failure_reason: Optional[str]
    started_at: str
    completed_at: Optional[str]
    progress_message: Optional[str] = None
    last_activity_at: Optional[str] = None
    partial_output: Optional[str] = None


class RunCreateResponse(BaseModel):
    id: str
    task_id: str
    mode: str
    status: str
    agent: str
    skill: str
    started_at: str
    completed_at: Optional[str]


class RunListResponse(BaseModel):
    runs: list[RunListItem]
