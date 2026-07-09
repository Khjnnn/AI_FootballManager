"""Claude CLI 헤드리스 분석기 (plan.md 7.1절).

로컬 Claude CLI(claude -p)를 호출해 경기별 리포트 14개 + 회차 종합 리포트를 생성한다.
구독 요금 내 처리 — 별도 API 키 불필요. 웹 검색으로 폼·전적·결장자를 조사한다.

실행: python -m analyzer.analyze --round 2026-38 [--match 3] [--skip-round-report]
산출: data/reports/{key}/M01.md … M14.md, summary.json, round.md
"""
import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from analyzer.prompts import build_match_prompt, build_round_prompt

log = logging.getLogger(__name__)
ROOT = Path(__file__).parent.parent
MATCHES_DIR = ROOT / "data" / "matches"
REPORTS_DIR = ROOT / "data" / "reports"

CLAUDE_TIMEOUT_SEC = 900
DISCLAIMER = "\n\n---\n*본 분석은 통계적 참고 자료이며 구매 결과를 보장하지 않습니다.*\n"

JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
# 로컬 Claude CLI에 설치된 훅/플러그인이 붙이는 상용구(bkit 푸터 등) 제거
BOILERPLATE = re.compile(r"─{10,}\s*\n📊[^\n]*\n.*?─{10,}\s*", re.DOTALL)


def clean_report(report: str) -> str:
    return BOILERPLATE.sub("", report).strip()


def call_claude(prompt: str, allow_web: bool = True) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude CLI를 찾을 수 없습니다 (claude 로그인 필요)")
    cmd = [exe, "-p"]
    if allow_web:
        cmd += ["--allowedTools", "WebSearch,WebFetch"]
    # 구독 로그인 사용 원칙(7.1절): 상속된 API 키·중첩 세션 변수를 제거해
    # claude.ai 로그인 세션으로 실행되도록 한다
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDECODE",
                        "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT")}
    res = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                         encoding="utf-8", timeout=CLAUDE_TIMEOUT_SEC, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"claude 실행 실패({res.returncode}): {res.stderr[:500]}")
    return res.stdout


def extract_summary(report: str) -> dict | None:
    """리포트 말미의 ```json 블록 → 구조화 요약 (7.2절 출력 이중 구조)."""
    blocks = JSON_BLOCK.findall(report)
    if not blocks:
        return None
    try:
        s = json.loads(blocks[-1])
        probs = s.get("probs", {})
        if not 0.99 <= sum(probs.get(k, 0) for k in ("win", "draw", "lose")) <= 1.01:
            return None
        if s.get("pick") not in ("win", "draw", "lose"):
            return None
        return s
    except json.JSONDecodeError:
        return None


def analyze_match(pkg: dict, out_dir: Path) -> dict | None:
    no = pkg["match_no"]
    name = f"M{no:02d}"
    if pkg.get("status") in ("cancelled", "postponed"):
        log.info("%s 취소·연기 — 적특 예상, 분석 생략", name)
        return {"match_no": no, "void": True}

    prompt = build_match_prompt(pkg)
    report = call_claude(prompt)
    summary = extract_summary(report)
    if summary is None:  # 형식 위반 시 1회 재요청 (7.2절)
        log.warning("%s JSON 블록 파싱 실패 — 재요청", name)
        report = call_claude(
            prompt + "\n\n중요: 반드시 응답 맨 끝에 지정된 ```json 코드블록을 출력하라.")
        summary = extract_summary(report)

    (out_dir / f"{name}.md").write_text(clean_report(report) + DISCLAIMER, encoding="utf-8")
    if summary is None:
        log.error("%s 구조화 요약 실패 — 종합 리포트에서 제외됨", name)
    return summary


def analyze_round(key: str, only_match: int | None = None,
                  skip_round_report: bool = False):
    pkg_dir = MATCHES_DIR / key
    if not pkg_dir.exists():
        sys.exit(f"입력 패키지 없음: {pkg_dir} (final_collect 선행 필요)")
    out_dir = REPORTS_DIR / key
    out_dir.mkdir(parents=True, exist_ok=True)

    packages = [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(pkg_dir.glob("M*.json"))]
    if only_match:
        packages = [p for p in packages if p["match_no"] == only_match]

    summary_path = out_dir / "summary.json"
    summaries = (json.loads(summary_path.read_text(encoding="utf-8"))
                 if summary_path.exists() else {})
    for pkg in packages:
        name = f"M{pkg['match_no']:02d}"
        if name in summaries and (out_dir / f"{name}.md").exists():
            log.info("%s 이미 분석됨 — 건너뜀 (재분석은 리포트 삭제 후)", name)
            continue
        log.info("%s 분석 시작: %s vs %s", name,
                 pkg["home"]["betman_name"], pkg["away"]["betman_name"])
        s = analyze_match(pkg, out_dir)
        if s:
            summaries[name] = s
            summary_path.write_text(
                json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")

    if skip_round_report or only_match:
        return
    done = [s for s in summaries.values() if not s.get("void")]
    if len(done) < len([p for p in packages if p.get("status") == "scheduled"]):
        log.warning("경기별 분석 미완 — 종합 리포트 생략")
        return
    meta = [{"match_no": p["match_no"], "league": p["league"],
             "home": p["home"]["betman_name"], "away": p["away"]["betman_name"],
             "vote_dist": {k: p["vote_dist"].get(k) for k in ("win", "draw", "lose")},
             "market_implied": (p.get("market_odds") or {}).get("implied_prob"),
             "status": p.get("status")} for p in packages]
    log.info("회차 종합 리포트 생성")
    round_report = call_claude(
        build_round_prompt(key, list(summaries.values()), meta), allow_web=False)
    (out_dir / "round.md").write_text(clean_report(round_report) + DISCLAIMER, encoding="utf-8")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", required=True, help="예: 2026-38")
    ap.add_argument("--match", type=int, help="특정 경기만 (1~14)")
    ap.add_argument("--skip-round-report", action="store_true")
    args = ap.parse_args()
    analyze_round(args.round, args.match, args.skip_round_report)


if __name__ == "__main__":
    main()
