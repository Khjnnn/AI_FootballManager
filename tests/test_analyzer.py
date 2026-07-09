"""분석기 출력 파싱·프롬프트 테스트 (Claude 호출 없음)."""
import json
from pathlib import Path

from analyzer.analyze import extract_summary
from analyzer.prompts import build_match_prompt, build_round_prompt

FIXTURES = Path(__file__).parent / "fixtures"

VALID_JSON = """분석 내용...

```json
{"match_no": 1, "probs": {"win": 0.35, "draw": 0.3, "lose": 0.35},
 "pick": "lose", "backup_pick": "draw", "confidence": "중",
 "expected_scores": ["1-1"], "key_factors": ["폼"], "data_gaps": []}
```"""


def test_extract_valid():
    s = extract_summary(VALID_JSON)
    assert s and s["pick"] == "lose" and s["confidence"] == "중"


def test_extract_uses_last_block():
    text = "```json\n{\"pick\": \"win\"}\n```\n중간 설명\n" + VALID_JSON
    s = extract_summary(text)
    assert s and s["match_no"] == 1


def test_extract_rejects_bad_probs():
    bad = VALID_JSON.replace('"win": 0.35', '"win": 0.85')  # 합 > 1
    assert extract_summary(bad) is None


def test_extract_rejects_bad_pick():
    bad = VALID_JSON.replace('"pick": "lose"', '"pick": "home"')
    assert extract_summary(bad) is None


def test_extract_rejects_no_block():
    assert extract_summary("JSON 블록 없는 응답") is None


def test_match_prompt_contains_package():
    pkg = {"match_no": 3, "home": {"betman_name": "광주FC"},
           "away": {"betman_name": "포항스틸"}, "vote_dist": {"win": 0.1},
           "market_odds": None, "research_needed": ["최근 폼"]}
    p = build_match_prompt(pkg)
    assert "광주FC" in p and "research_needed" in p and '"match_no": 3' in p
    assert "웹 검색" in p  # 리서치 지시 포함


def test_round_prompt_contains_summaries():
    p = build_round_prompt("2026-38",
                           [{"match_no": 1, "pick": "win"}],
                           [{"match_no": 1, "home": "울산HDFC"}])
    assert "2026-38" in p and "울산HDFC" in p and "적특 예상" in p
