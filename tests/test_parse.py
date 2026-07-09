import json
from datetime import timedelta
from pathlib import Path

import pytest

from collector.parse import extract_g011_gmts, parse_round

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def raw_round():
    return json.loads((FIXTURES / "totoGameData_260038.json").read_text(encoding="utf-8"))


@pytest.fixture
def raw_buyable():
    return json.loads((FIXTURES / "buyableGameList.json").read_text(encoding="utf-8"))


def test_round_meta(raw_round):
    r = parse_round(raw_round)
    assert r.round_id == "260038"
    assert r.year == 2026
    assert r.round_no == 38
    assert r.game_id == "G011"


def test_kst_timezone_and_analysis_due(raw_round):
    r = parse_round(raw_round)
    assert r.sale_close.utcoffset() == timedelta(hours=9)  # KST 고정
    assert r.sale_close - r.analysis_due == timedelta(hours=12)  # 마감 −12h


def test_fourteen_matches(raw_round):
    r = parse_round(raw_round)
    assert len(r.matches) == 14
    assert [m.match_no for m in r.matches] == list(range(1, 15))


def test_vote_dist_sums_to_one(raw_round):
    r = parse_round(raw_round)
    for m in r.matches:
        vals = [v for v in m.vote_dist.values() if v is not None]
        assert 0.99 <= sum(vals) <= 1.01, f"M{m.match_no} 분포 합 이상"


def test_match_fields(raw_round):
    m1 = parse_round(raw_round).matches[0]
    assert m1.home.betman_name and m1.away.betman_name
    assert m1.league
    assert m1.kickoff.year == 2026
    assert m1.status == "scheduled"


def test_schema_rejects_missing_matches(raw_round):
    raw_round["schedulesList"] = raw_round["schedulesList"][:13]
    raw_round["voteStatus"]["homeVoteStatusList"] = \
        raw_round["voteStatus"]["homeVoteStatusList"][:13]
    with pytest.raises(ValueError, match="경기 수"):
        parse_round(raw_round)


def test_status_mapping(raw_round):
    raw_round["schedulesList"][0]["gameReject"] = "Y"       # 취소
    raw_round["schedulesList"][1]["unsetSchedule"] = "Y"    # 연기
    r = parse_round(raw_round)
    assert r.matches[0].status == "cancelled"
    assert r.matches[1].status == "postponed"
    assert all(m.status == "scheduled" for m in r.matches[2:])


def test_detect_g011(raw_buyable):
    assert extract_g011_gmts(raw_buyable) == 260038


def test_detect_no_g011():
    assert extract_g011_gmts({"totoGames": []}) is None
