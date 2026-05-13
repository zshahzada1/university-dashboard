from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

ISODate = str  # "YYYY-MM-DD"
ISOTime = str  # "HH:MM"
ISODateTime = str  # full ISO 8601

class Module(BaseModel):
    code: str
    name: str
    color: str
    folder: str

class Topic(BaseModel):
    id: str
    title: str
    week: Optional[int] = None
    folder: str
    confidence: Optional[int] = Field(default=None, ge=1, le=5)
    updated_at: Optional[ISODateTime] = None

class Assignment(BaseModel):
    id: str
    module_code: str
    assignment_title: str
    assignment_type: str
    description: str = ""
    deadline_date: ISODate
    deadline_time: ISOTime = "23:59"
    weighting_percent: float = 0
    word_limit_or_size: str = ""
    submission_method: str = ""
    status: Literal["upcoming", "submitted", "graded"] = "upcoming"
    linked_topics: list[str] = []

class Task(BaseModel):
    id: str
    text: str
    module_code: Optional[str] = None
    topic_id: Optional[str] = None
    due_date: Optional[ISODate] = None
    done: bool = False
    created_at: ISODateTime

class Event(BaseModel):
    id: str
    title: str
    date: ISODate
    time: Optional[ISOTime] = None
    module_code: Optional[str] = None
    kind: Literal["exam", "meeting", "study_session", "other"] = "other"