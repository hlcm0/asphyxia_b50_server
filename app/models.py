from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlayerSummary(BaseModel):
    refid: str
    name: str
    sdvxId: int
    scoreCount: int


class B50Card(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rank: int
    mid: int
    difficultyNum: int | None = None
    title: str
    difficultyLabel: str
    level: str
    score: int
    clearLamp: str
    singleVf: str


class UploadClientInfo(BaseModel):
    app: str
    uploadAt: str


class B50UploadRequest(BaseModel):
    schemaVersion: Literal[1, 2]
    game: Literal["sdvx"]
    version: Literal[7]
    qq: str = Field(pattern=r"^[0-9]{5,12}$")
    player: PlayerSummary
    totalVf: str
    generatedAt: str
    cards: list[B50Card]
    client: UploadClientInfo
    serverUrl: str | None = None
    cardNo: str | None = None
    password: str | None = None
    pcbid: str | None = None

    @field_validator("cards")
    @classmethod
    def cards_must_not_be_empty(cls, value: list[B50Card]) -> list[B50Card]:
        if not value:
            raise ValueError("cards must not be empty")
        return value


class ApiResponse(BaseModel):
    ok: bool
    message: str


class LatestB50Response(ApiResponse):
    data: dict[str, Any]
