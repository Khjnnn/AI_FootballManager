"""totoGameData.do 응답 → 회차 JSON 파서 PoC.

plan.md 6절 스키마 기반. 승무패(G011)는 고정 배당이 없어
betman_odds 대신 vote_dist(대중 투표 분포)를 기록한다.

실행: python poc/parse_round.py [응답파일]
산출: data/rounds/{year}-{round}.json
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).parent.parent


def ms_to_kst(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=KST).isoformat()


def parse(raw: dict) -> dict:
    cl = raw["currentLottery"]
    year = cl["gmOsidTsYear"]
    round_no = cl["gmOsidTs"]
    sale_close_ms = cl["saleEndDate"]

    schedules = raw["schedulesList"]
    votes = raw["voteStatus"]["homeVoteStatusList"]
    assert len(schedules) == 14, f"경기 수 이상: {len(schedules)}"
    assert len(votes) == 14, f"투표 데이터 수 이상: {len(votes)}"

    matches = []
    for i, (m, v) in enumerate(zip(schedules, votes), start=1):
        counts = [a["voteCount"] for a in v["awayVoteStatusList"]]
        total = sum(counts)
        dist = {k: round(c / total, 4) if total else None
                for k, c in zip(("win", "draw", "lose"), counts)}
        matches.append({
            "match_no": i,
            "match_seq": m["matchSeq"],
            "league": m["leagueName"],
            "league_code": m["leagueCode"],
            "domestic": m["domastic"],
            "kickoff": ms_to_kst(m["gameDate"]),
            "home": {"betman_name": m["homeName"], "id": m["homeId"], "canonical": None},
            "away": {"betman_name": m["awayName"], "id": m["awayId"], "canonical": None},
            "stadium": m.get("meetStadium"),
            "handicap": m.get("handi", 0),
            "status": "scheduled",
            "vote_counts": {"win": counts[0], "draw": counts[1], "lose": counts[2]},
            "vote_dist": dist,
        })

    return {
        "round_id": str(cl["gmTs"]),
        "year": year,
        "round_no": round_no,
        "game_id": "G011",
        "sale_open": ms_to_kst(cl["saleStartDate"]),
        "sale_close": ms_to_kst(sale_close_ms),
        "analysis_due": ms_to_kst(sale_close_ms - 12 * 3600 * 1000),
        "status": "on_sale",
        "collected_at": ms_to_kst(raw["standardDate"]),
        "matches": matches,
    }


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(__file__).parent / "captures" / "006_totoGameData.do"
    raw = json.loads(src.read_text(encoding="utf-8"))
    round_data = parse(raw)

    out = ROOT / "data" / "rounds" / f"{round_data['year']}-{round_data['round_no']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(round_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"round {round_data['year']}년 {round_data['round_no']}회차 "
          f"(마감 {round_data['sale_close']}, 분석시점 {round_data['analysis_due']})")
    for m in round_data["matches"]:
        d = m["vote_dist"]
        print(f"  M{m['match_no']:02d} [{m['league']}] "
              f"{m['home']['betman_name']} vs {m['away']['betman_name']} "
              f"{m['kickoff'][:16]} 투표 {d['win']:.0%}/{d['draw']:.0%}/{d['lose']:.0%}")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
