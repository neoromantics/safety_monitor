from pydantic import BaseModel
from datetime import datetime

class EventBase(BaseModel):
    type: str
    confidence: float
    source: str
    model_info: str

class EventCreate(EventBase):
    pass

class EventResponse(EventBase):
    id: int
    timestamp: datetime
    status: str

    class Config:
        from_attributes = True

class EventUpdate(BaseModel):
    status: str
