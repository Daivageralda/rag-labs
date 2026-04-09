from pydantic import BaseModel


class QueryRequest(BaseModel):
    user_id: str
    query: str


class AddDocRequest(BaseModel):
    text: str
