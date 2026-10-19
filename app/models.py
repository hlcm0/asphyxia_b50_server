from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class ScorePlayer(BaseModel):
    refid: str
    name: str
    sdvxId: int


class ScoreRecord(BaseModel):
    """A chart's best record as the game server keeps it (one sv7_load_m entry)."""

    model_config = ConfigDict(extra="ignore")

    mid: int = Field(ge=0)
    type: int = Field(ge=0, le=5)
    score: int = Field(ge=0, le=10_000_000)
    exscore: int = Field(default=0, ge=0)
    clear: int = Field(default=0, ge=0)
    grade: int = Field(default=0, ge=0)
    buttonRate: int = 0
    longRate: int = 0
    volRate: int = 0
    # The game's own value; only used for charts without difnum.
    volforce: int = Field(default=0, ge=0)
    title: str | None = None
    difficultyLabel: str | None = None
    # music_db.xml <difnum>: the level times 10 (185 = 18.5).
    difnum: int | None = Field(default=None, ge=0)


class ScorePlay(ScoreRecord):
    """One played track (one sv7_save_m <track>), with the judgement counts of that play."""

    model_config = ConfigDict(extra="allow")

    uid: str = Field(pattern=r"^[0-9A-Za-z_-]{8,64}$")
    playedAt: str
    maxChain: int = Field(default=0, ge=0)
    sCritical: int = Field(default=0, ge=0)
    critical: int = Field(default=0, ge=0)
    near: int = Field(default=0, ge=0)
    error: int = Field(default=0, ge=0)


class ScoreUploadRequest(BaseModel):
    schemaVersion: Literal[1]
    game: Literal["sdvx"]
    version: Literal[7]
    qq: str = Field(pattern=r"^[0-9]{5,12}$")
    player: ScorePlayer
    records: list[ScoreRecord] = Field(default_factory=list, max_length=50_000)
    plays: list[ScorePlay] = Field(default_factory=list, max_length=1_000)
    client: UploadClientInfo

    @model_validator(mode="after")
    def must_carry_scores(self) -> "ScoreUploadRequest":
        if not self.records and not self.plays:
            raise ValueError("records and plays must not both be empty")
        return self


class ApiResponse(BaseModel):
    ok: bool
    message: str


class LatestB50Response(ApiResponse):
    data: dict[str, Any]


class ScoreUploadResponse(ApiResponse):
    records: int
    plays: int
    b50Updated: bool


class DataResponse(ApiResponse):
    data: dict[str, Any]
