"""totoGameData.do 원시 응답 → Round 모델 변환."""
import logging
from datetime import datetime, timedelta, timezone

from .models import Match, MatchStatus, Round, TeamRef, VoteCounts

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
ANALYSIS_LEAD_HOURS = 12


def ms_to_kst(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=KST)


def map_status(m: dict) -> MatchStatus:
    """배트맨 경기 상태 필드 → 내부 상태 (plan.md 6.3절).

    취소·연기 경기는 적특 처리되므로 분석에서 제외하고 사이트에 표기한다.
    필드 의미는 PoC 관찰 기반 보수적 매핑 — 미지의 matchState 값은 로그로 남겨
    실회차 운영에서 매핑을 보강한다.
    """
    if m.get("gameReject") == "Y" or m.get("buyReject") == "Y":
        return "cancelled"
    if m.get("unsetSchedule") == "Y":
        return "postponed"
    state = m.get("matchState")
    if state not in (None, "", "0"):
        log.warning("미지의 matchState=%r (matchSeq=%s) — 매핑 보강 필요",
                    state, m.get("matchSeq"))
    return "scheduled"


def parse_round(raw: dict) -> Round:
    cl = raw["currentLottery"]
    schedules = raw["schedulesList"]
    votes = raw["voteStatus"]["homeVoteStatusList"]

    matches = []
    for i, (m, v) in enumerate(zip(schedules, votes), start=1):
        counts = [a["voteCount"] for a in v["awayVoteStatusList"]]
        total = sum(counts)
        dist = {k: round(c / total, 4) if total else None
                for k, c in zip(("win", "draw", "lose"), counts)}
        matches.append(Match(
            match_no=i,
            match_seq=m["matchSeq"],
            league=m["leagueName"],
            league_code=m.get("leagueCode"),
            domestic=m.get("domastic"),
            kickoff=ms_to_kst(m["gameDate"]),
            home=TeamRef(betman_name=m["homeName"], id=m.get("homeId")),
            away=TeamRef(betman_name=m["awayName"], id=m.get("awayId")),
            stadium=m.get("meetStadium"),
            handicap=m.get("handi", 0) or 0,
            status=map_status(m),
            vote_counts=VoteCounts(win=counts[0], draw=counts[1], lose=counts[2]),
            vote_dist=dist,
        ))

    sale_close = ms_to_kst(cl["saleEndDate"])
    return Round(
        round_id=str(cl["gmTs"]),
        year=cl["gmOsidTsYear"],
        round_no=cl["gmOsidTs"],
        sale_open=ms_to_kst(cl["saleStartDate"]),
        sale_close=sale_close,
        analysis_due=sale_close - timedelta(hours=ANALYSIS_LEAD_HOURS),
        collected_at=ms_to_kst(raw["standardDate"]),
        matches=matches,
    )


def extract_g011_gmts(buyable_raw: dict) -> int | None:
    """inqBuyAbleGameInfoList.do 응답에서 발매 중인 G011 회차의 gmTs를 찾는다."""
    for g in buyable_raw.get("totoGames") or []:
        if (g.get("gameMaster") or {}).get("gmId") == "G011":
            return g.get("gmTs")
    return None
