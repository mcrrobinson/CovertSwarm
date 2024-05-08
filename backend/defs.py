from pydantic import BaseModel


class Job(BaseModel):
    args: str


class UpdateJob(BaseModel):
    uuid: str
    status: str
    task: str
