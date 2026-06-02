from pydantic import BaseModel, Field


class MaomaniB50Request(BaseModel):
    cardNo: str = Field(min_length=1)
