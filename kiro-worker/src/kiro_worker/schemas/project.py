from pydantic import BaseModel
from typing import Optional, List
from kiro_worker.domain.enums import Source


class ProjectCreate(BaseModel):
    name: str
    source: Source
    source_url: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    source: str
    source_url: Optional[str]
    workspace_id: Optional[str]
    owner_id: Optional[str]
    aliases: List[str] = []
    created_at: str
    updated_at: str


class SourceUrlUpdate(BaseModel):
    source_url: str


class AliasSet(BaseModel):
    alias: str


class AliasRemove(BaseModel):
    alias: str
