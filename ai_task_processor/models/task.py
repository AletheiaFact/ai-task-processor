from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskType(str, Enum):
    TEXT_EMBEDDING = "text_embedding"


class CallbackRoute(str, Enum):
    VERIFICATION_UPDATE_EMBEDDING = "verification_update_embedding"


class Task(BaseModel):
    id: str = Field(alias="_id")
    type: TaskType
    status: TaskStatus = Field(alias="state")
    content: Optional[Any] = None
    callback_route: CallbackRoute = Field(alias="callbackRoute")
    callback_params: Dict[str, Any] = Field(alias="callbackParams")
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")
    
    class Config:
        populate_by_name = True


class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class TextEmbeddingInput(BaseModel):
    text: str
    model: str = "text-embedding-3-small"


class TextEmbeddingOutput(BaseModel):
    embedding: List[float]
    model: str
    usage: Dict[str, int]