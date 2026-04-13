from pydantic import BaseModel
from typing import Optional


class WorkspaceCreate(BaseModel):
    git_branch: Optional[str] = None


class WorkspaceResponse(BaseModel):
    id: str
    project_id: str
    path: str
    git_remote: Optional[str]
    git_branch: Optional[str]
    created_at: str
    last_accessed_at: str
    reuse_decision: Optional[str] = None  # "reused" | "created" | "existing"
