"""해외 배당 수집기 테스트 — 캡처 픽스처 기반, 네트워크 없음."""
import json
from pathlib import Path

import pytest

from collector.odds import collect_market_odds, consensus_odds
from collector.parse import parse_round

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def round_2026_38():
    raw = json.loads((FIXTURES / "totoGameData_260038.json").read_text(encoding="utf-8"))
    return parse_round(raw)


@pytest.fixture
def events():
    out = []
    for f in ("odds_soccer_korea_kleague1.json", "odds_soccer_norway_eliteserien.json"):
        out.extend(json.loads((FIXTURES / f).read_text(encoding="utf-8")))
    return out


def test_covered_matches(round_2026_38, events):
    market = collect_market_odds(round_2026_38, events)
    covered = [no for no, v in market.items() if v is not None]
    # K리그1 6경기(M01~03, M10~12) + 노르웨이 2경기(M08~09)
    assert covered == [1, 2, 3, 8, 9, 10, 11, 12]


def test_k2_matches_are_none(round_2026_38, events):
    market = collect_market_odds(round_2026_38, events)
    for no in (4, 5, 6, 7, 13, 14):
        assert market[no] is None


def test_implied_prob_normalized(round_2026_38, events):
    market = collect_market_odds(round_2026_38, events)
    for no, mo in market.items():
        if mo is None:
            continue
        s = sum(mo["implied_prob"].values())
        assert 0.999 <= s <= 1.001, f"M{no} 내재확률 합 {s}"
        assert mo["bookmakers"] >= 5  # 충분한 북메이커 수


def test_consensus_median(events):
    ev = next(e for e in events if e["home_team"] == "Ulsan Hyundai FC")
    mo = consensus_odds(ev, "Ulsan Hyundai FC", "Jeonbuk Hyundai Motors")
    assert mo and mo["win"] > 1.0 and mo["draw"] > 1.0 and mo["lose"] > 1.0


def test_unmapped_team_warns(round_2026_38, events, caplog):
    r = round_2026_38.model_copy(deep=True)
    r.matches[0].home.betman_name = "없는팀"
    with caplog.at_level("WARNING"):
        market = collect_market_odds(r, events)
    assert market[1] is None
    assert any("팀 매핑 누락" in rec.message for rec in caplog.records)
