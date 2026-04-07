from pydantic import BaseModel
from typing import Optional, Any


class ArtifactResponse(BaseModel):
    id: str
    run_id: str
    task_id: str
    type: str
    schema_version: str
    content: Any
    file_path: Optional[str]
    created_at: str
