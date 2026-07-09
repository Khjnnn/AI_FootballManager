"""The Odds API 해외 배당 수집기 (plan.md 4.3절).

회차의 각 경기를 teams.yaml 매핑으로 The Odds API 이벤트와 대조해
북메이커 중앙값 배당과 내재확률(마진 제거)을 계산한다.
K리그2 등 미커버 리그는 None → 분석 프롬프트가 결측을 명시한다.
"""
import logging
import os
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import yaml

from .models import Round

log = logging.getLogger(__name__)
ROOT = Path(__file__).parent.parent
KST = timezone(timedelta(hours=9))

BASE = "https://api.the-odds-api.com/v4"
SPORTS = ["soccer_korea_kleague1", "soccer_norway_eliteserien"]
KICKOFF_TOLERANCE = timedelta(hours=3)


def load_env() -> dict:
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    env.update(os.environ)
    return env


def load_teams() -> dict:
    return yaml.safe_load((ROOT / "config" / "teams.yaml").read_text(encoding="utf-8"))


def fetch_events(api_key: str) -> list[dict]:
    """커버 리그의 h2h 배당 이벤트 전체 조회 (스포츠당 크레딧 1)."""
    events = []
    with httpx.Client(timeout=30) as client:
        for sport in SPORTS:
            r = client.get(f"{BASE}/sports/{sport}/odds",
                           params={"apiKey": api_key, "regions": "eu",
                                   "markets": "h2h", "oddsFormat": "decimal"})
            r.raise_for_status()
            log.info("odds-api %s: 잔여 크레딧 %s", sport,
                     r.headers.get("x-requests-remaining"))
            events.extend(r.json())
    return events


def consensus_odds(event: dict, home: str, away: str) -> dict | None:
    """북메이커별 h2h 배당의 중앙값 → 마진 제거 내재확률."""
    win, draw, lose = [], [], []
    for bm in event.get("bookmakers", []):
        for mk in bm.get("markets", []):
            if mk["key"] != "h2h":
                continue
            prices = {o["name"]: o["price"] for o in mk["outcomes"]}
            if home in prices and away in prices and "Draw" in prices:
                win.append(prices[home])
                draw.append(prices["Draw"])
                lose.append(prices[away])
    if not win:
        return None
    w, d, l = (statistics.median(x) for x in (win, draw, lose))
    raw = [1 / w, 1 / d, 1 / l]
    total = sum(raw)
    return {
        "win": round(w, 2), "draw": round(d, 2), "lose": round(l, 2),
        "implied_prob": {k: round(p / total, 4)
                         for k, p in zip(("win", "draw", "lose"), raw)},
        "bookmakers": len(win),
        "source": "the-odds-api(eu median)",
    }


def collect_market_odds(r: Round, events: list[dict] | None = None) -> dict[int, dict | None]:
    """회차 14경기 → {match_no: market_odds | None}."""
    teams = load_teams()
    if events is None:
        events = fetch_events(load_env()["ODDS_API_KEY"])

    out: dict[int, dict | None] = {}
    for m in r.matches:
        h_map = teams.get(m.home.betman_name) or {}
        a_map = teams.get(m.away.betman_name) or {}
        if not h_map or not a_map:
            log.warning("팀 매핑 누락: %s / %s — teams.yaml 보완 필요",
                        m.home.betman_name, m.away.betman_name)
        h, a = h_map.get("odds_api"), a_map.get("odds_api")
        if not h or not a:
            out[m.match_no] = None  # 미커버 리그
            continue
        found = None
        for ev in events:
            if ev["home_team"] == h and ev["away_team"] == a:
                ko = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
                if abs(ko - m.kickoff) <= KICKOFF_TOLERANCE:
                    found = consensus_odds(ev, h, a)
                    if found:
                        found["collected_at"] = datetime.now(KST).isoformat()
                    break
        if found is None:
            log.warning("M%02d %s vs %s: 커버 리그이나 이벤트 미발견",
                        m.match_no, m.home.betman_name, m.away.betman_name)
        out[m.match_no] = found
    return out
