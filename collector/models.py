"""수집 데이터 pydantic 스키마 (plan.md 6절·6.1절).

모든 수집 응답은 이 모델 검증을 통과해야 하며,
검증 실패가 Playwright 폴백과 알림을 트리거하는 단일 관문이다.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

MatchStatus = Literal["scheduled", "postponed", "cancelled", "finished"]


class TeamRef(BaseModel):
    betman_name: str
    id: Optional[str] = None
    canonical: Optional[str] = None


class VoteCounts(BaseModel):
    win: int = Field(ge=0)
    draw: int = Field(ge=0)
    lose: int = Field(ge=0)

    @property
    def total(self) -> int:
        return self.win + self.draw + self.lose


class Match(BaseModel):
    match_no: int = Field(ge=1, le=14)
    match_seq: int
    league: str
    league_code: Optional[str] = None
    domestic: Optional[bool] = None
    kickoff: datetime
    home: TeamRef
    away: TeamRef
    stadium: Optional[str] = None
    handicap: float = 0
    status: MatchStatus = "scheduled"
    vote_counts: VoteCounts
    vote_dist: dict[str, Optional[float]]

    @field_validator("vote_dist")
    @classmethod
    def dist_sums_to_one(cls, v):
        vals = [x for x in v.values() if x is not None]
        if vals and not 0.99 <= sum(vals) <= 1.01:
            raise ValueError(f"투표 분포 합 이상: {sum(vals)}")
        return v


class Round(BaseModel):
    round_id: str
    year: int
    round_no: int
    game_id: str = "G011"
    sale_open: datetime
    sale_close: datetime
    analysis_due: datetime
    status: str = "on_sale"
    collected_at: datetime
    matches: list[Match]

    @field_validator("matches")
    @classmethod
    def must_have_14(cls, v):
        if len(v) != 14:
            raise ValueError(f"경기 수 이상: {len(v)} (14이어야 함)")
        return v
