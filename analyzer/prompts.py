"""분석 프롬프트 v1 (plan.md 7.2절).

경기별: 입력 패키지 + 웹 리서치 지시 → 서술 마크다운 + 기계가독 JSON.
종합: 경기별 JSON 14개 → 회차 종합 리포트.
"""
import json

MATCH_PROMPT = """당신은 축구 승무패 분석 전문가다. 아래 JSON은 한 경기의 데이터다.
배트맨 승무패는 고정 배당이 없는 패리뮤추얼 방식이라 vote_dist(대중 투표 분포)가 제공되며,
market_odds는 해외 북메이커 중앙값 배당과 내재확률이다 (null이면 해외 배당 미커버 리그).

{package}

## 1단계: 최신 정보 조사 (웹 검색 사용)
research_needed 항목을 웹 검색으로 조사하라. 팀명은 betman_name(한글)과 canonical(영문)을 활용하라.
- 양 팀의 최근 5경기 결과(폼), 최근 상대 전적
- 현재 리그 순위·승점 (강등권/우승 경쟁 등 동기)
- 결장자: 부상·출전정지 (가장 최신 뉴스 기준, 날짜 확인)
- 일정 피로도: 직전·직후 일정, 컵대회, 로테이션 가능성
검색으로 확인 못 한 항목은 추정하지 말고 결측으로 명시하라.

## 2단계: 다음 구조로 분석 (한국어 마크다운)
1. 경기 개요 — 리그 맥락, 양 팀의 현재 상황과 동기
2. 전력 비교 — 최근 폼, 홈/원정 성적, 상대 전적의 시사점 (조사 결과 근거)
3. 변수 — 결장자 영향, 일정 피로도, 로테이션 가능성
4. 시장·대중 해석 — 대중 투표 분포(vote_dist)와 해외 시장 확률(market_odds)의 괴리,
   시장이 보는 방향과 대중 쏠림 (market_odds가 null이면 투표 분포만으로 해석하고 한계 명시)
5. 예측 — 승/무/패 확률(합 100%), 예상 스코어 1~2개, 최종 픽과 보조 픽
6. 신뢰도 — 상/중/하 및 그 근거 (데이터 결측이 있으면 반드시 명시)

주의: 확률은 시장 내재확률(없으면 투표 분포)을 기준선으로 삼고, 조사로 확인된 요인만으로 조정하라.
과신하지 말고 불확실성을 정직하게 기술하라.

## 3단계: 응답 맨 끝에 아래 형식의 JSON 코드블록을 정확히 출력
```json
{{
  "match_no": {match_no},
  "probs": {{"win": 0.00, "draw": 0.00, "lose": 0.00}},
  "pick": "win|draw|lose",
  "backup_pick": "win|draw|lose",
  "confidence": "상|중|하",
  "expected_scores": ["1-0", "2-1"],
  "key_factors": ["요인 1", "요인 2"],
  "data_gaps": ["결측 항목"]
}}
```"""

ROUND_PROMPT = """당신은 축구 승무패 분석 편집자다. 아래는 이번 회차({round_key}) 14경기의
경기별 분석 결과 JSON 배열이다. matches_meta는 대진 정보다.

[분석 결과]
{summaries}

[대진 정보]
{matches_meta}

다음 구조로 회차 종합 리포트를 작성하라 (한국어 마크다운):
1. 회차 요약 표 — 경기번호, 대진, 최종 픽, 확률, 신뢰도
2. 신뢰도 상위 3경기 — 픽과 근거 요약
3. 이변 후보 — 시장/투표 확률 대비 업셋 가능성이 있는 경기와 이유
4. 투표-시장 괴리 상위 — 대중 투표 분포와 해외 시장 확률의 차이가 큰 경기
   (해외 배당 미커버 경기는 제외하고 그 사실을 명시)
5. 종합 코멘트 — 이번 회차의 전반적 난이도와 유의점

수치는 경기별 JSON 값을 그대로 사용하고 새로 추정하지 마라.
취소·연기(적특) 경기는 표에 "적특 예상"으로만 표기하라."""


def build_match_prompt(package: dict) -> str:
    return MATCH_PROMPT.format(
        package=json.dumps(package, ensure_ascii=False, indent=1),
        match_no=package["match_no"])


def build_round_prompt(round_key: str, summaries: list[dict], matches_meta: list[dict]) -> str:
    return ROUND_PROMPT.format(
        round_key=round_key,
        summaries=json.dumps(summaries, ensure_ascii=False, indent=1),
        matches_meta=json.dumps(matches_meta, ensure_ascii=False, indent=1))
