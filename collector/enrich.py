"""분석 입력 패키지 생성·병합 (plan.md 4.3절·6절).

배트맨 회차 데이터(투표 분포)에 해외 배당을 병합해
data/matches/{key}/Mxx.json 입력 패키지를 만든다.

폼·상대전적·순위·결장자는 API-Football 무료 플랜의 시즌 제한(2022~2024)으로
수집 불가 → 분석 단계에서 Claude CLI의 웹 리서치로 조사한다 (v1.4 변경).
유료 플랜 전환 시 이 모듈에 병합 로직을 추가하면 된다.
"""
import json
import logging
from pathlib import Path

from .models import Round
from .odds import collect_market_odds, load_teams

log = logging.getLogger(__name__)
ROOT = Path(__file__).parent.parent
MATCHES_DIR = ROOT / "data" / "matches"


def build_packages(r: Round, events: list[dict] | None = None) -> Path:
    """회차 → 경기별 분석 입력 패키지 14개 생성. 반환: 패키지 디렉터리."""
    teams = load_teams()
    for m in r.matches:  # teams.yaml의 표준 영문명 채움 (웹 리서치용)
        m.home.canonical = (teams.get(m.home.betman_name) or {}).get("canonical")
        m.away.canonical = (teams.get(m.away.betman_name) or {}).get("canonical")
    market = collect_market_odds(r, events)
    key = f"{r.year}-{r.round_no}"
    pkg_dir = MATCHES_DIR / key
    pkg_dir.mkdir(parents=True, exist_ok=True)

    covered = 0
    for m in r.matches:
        mo = market.get(m.match_no)
        covered += mo is not None
        pkg = {
            "round": key,
            "match_no": m.match_no,
            "league": m.league,
            "kickoff": m.kickoff.isoformat(),
            "home": m.home.model_dump(),
            "away": m.away.model_dump(),
            "stadium": m.stadium,
            "status": m.status,
            "vote_dist": {**m.vote_dist,
                          "counts": m.vote_counts.model_dump(),
                          "collected_at": r.collected_at.isoformat()},
            "market_odds": mo,  # None = 해외 배당 미커버 (결측 명시 대상)
            "research_needed": ["최근 폼(최근 5경기)", "상대 전적", "리그 순위·승점",
                                "결장자(부상·징계)", "일정 피로도·로테이션 가능성"],
        }
        (pkg_dir / f"M{m.match_no:02d}.json").write_text(
            json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("%s 입력 패키지 14개 생성 (해외 배당 %d/14 커버)", key, covered)
    return pkg_dir
