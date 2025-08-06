from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskType(str, Enum):
    TEXT_EMBEDDING = "text-embedding"


class Task(BaseModel):
    id: str
    type: TaskType
    status: TaskStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    retry_count: int = 0


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