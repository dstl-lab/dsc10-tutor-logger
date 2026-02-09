from pydantic import BaseModel


class EventIn(BaseModel):
    event_type: str
    user_email: str | None = None
    payload: dict = {}
