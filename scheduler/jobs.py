"""회차 감지·최종 수집 잡 (plan.md 5절).

- detect_and_register: 매일 09:00 실행. 신규 회차 발견 시 저장 + "예정" 페이지
  빌드(7.5절 ①) + 마감−12h 최종 수집 잡 동적 등록.
- final_collect: 마감 −12h 실행. 최신 투표 분포로 재수집 + 경기별 분석 입력
  패키지 생성 + (설정 시) git push로 로컬 분석 트리거.
"""
import json
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.betman import BetmanClient
from collector.models import Round
from scheduler.notify import notify

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).parent.parent
ROUNDS_DIR = ROOT / "data" / "rounds"
MATCHES_DIR = ROOT / "data" / "matches"
REPORTS_DIR = ROOT / "data" / "reports"
WATCH_DELAY_HOURS = 1  # 최종 수집 후 1시간 뒤(= 마감−11h) 미완료 감시


def round_key(r: Round) -> str:
    return f"{r.year}-{r.round_no}"


def save_round(r: Round) -> Path:
    ROUNDS_DIR.mkdir(parents=True, exist_ok=True)
    path = ROUNDS_DIR / f"{round_key(r)}.json"
    path.write_text(r.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_saved_rounds() -> list[Round]:
    out = []
    for f in sorted(ROUNDS_DIR.glob("*.json")):
        try:
            out.append(Round.model_validate_json(f.read_text(encoding="utf-8")))
        except Exception as e:
            log.warning("회차 파일 로드 실패 %s: %s", f.name, e)
    return out


def rebuild_site():
    from site_builder.build import build_all
    build_all()


def detect_and_register(scheduler=None) -> Round | None:
    """신규 회차 감지. 발견 시 저장·예정 페이지 빌드·최종 수집 잡 등록."""
    client = BetmanClient()
    gmts = client.detect_g011_gmts()
    if gmts is None:
        log.info("발매 중인 G011 회차 없음")
        return None

    r = client.fetch_round(gmts)
    key = round_key(r)
    path = ROUNDS_DIR / f"{key}.json"
    is_new = not path.exists()
    if not is_new:
        check_composition_change(path, r)
    save_round(r)  # 기존 회차여도 최신 투표·마감시각으로 갱신 (6.3절 마감 변경 대응)
    rebuild_site()
    log.info("%s 회차 %s (마감 %s, 분석시점 %s)",
             "신규" if is_new else "갱신", key, r.sale_close, r.analysis_due)

    if scheduler is not None:
        register_round_jobs(scheduler, r)
    return r


def check_composition_change(prev_path: Path, new: Round):
    """회차 구성 변경 감지 (plan.md 6.3절): 대진·마감시각이 달라지면 경고."""
    try:
        prev = Round.model_validate_json(prev_path.read_text(encoding="utf-8"))
    except Exception:
        return
    key = round_key(new)
    pairs = lambda r: [(m.home.betman_name, m.away.betman_name) for m in r.matches]
    if pairs(prev) != pairs(new):
        notify(f"{key} 회차 대진 구성 변경 감지 — 회차 파일 갱신됨, 확인 필요")
    if prev.sale_close != new.sale_close:
        notify(f"{key} 마감 시각 변경: {prev.sale_close} → {new.sale_close} (잡 재예약됨)")


def register_round_jobs(scheduler, r: Round):
    """마감 −12h 최종 수집 잡 + 마감 −11h 미완료 감시 잡을 등록·재예약한다."""
    key = round_key(r)
    now = datetime.now(KST)
    if r.analysis_due > now:
        scheduler.add_job(
            final_collect, "date", run_date=r.analysis_due,
            args=[key], id=f"final-{key}", replace_existing=True,
        )
        log.info("%s 최종 수집 잡 등록: %s", key, r.analysis_due)
    else:
        log.info("%s 분석 시점 경과 — 최종 수집 잡 미등록", key)

    watch_at = r.analysis_due + timedelta(hours=WATCH_DELAY_HOURS)  # = 마감−11h
    if watch_at > now:
        scheduler.add_job(
            watch_report, "date", run_date=watch_at,
            args=[key], id=f"watch-{key}", replace_existing=True,
        )
        log.info("%s 미완료 감시 잡 등록: %s", key, watch_at)


def watch_report(key: str):
    """마감 −11h: 로컬 분석 리포트 커밋 부재 시 경보 (plan.md 5절, 3절 안전망)."""
    subprocess.run(["git", "pull", "--ff-only"], cwd=ROOT, capture_output=True)
    report_dir = REPORTS_DIR / key
    if report_dir.exists() and any(report_dir.iterdir()):
        log.info("%s 리포트 확인됨 — 정상", key)
        return
    notify(f"{key} 회차 리포트가 아직 생성되지 않았습니다 (마감 11시간 전). "
           f"로컬 PC 상태를 확인하고 필요 시 수동 실행: analyze --round {key}")


def final_collect(key: str):
    """마감 −12h: 최신 재수집 → 해외 배당 병합 입력 패키지 → git push(설정 시)."""
    from collector.enrich import build_packages

    path = ROUNDS_DIR / f"{key}.json"
    prev = Round.model_validate_json(path.read_text(encoding="utf-8"))
    r = BetmanClient().fetch_round(int(prev.round_id))
    save_round(r)

    try:
        build_packages(r)
    except Exception as e:
        notify(f"{key} 해외 배당 수집 실패({e}) — 배당 결측 패키지로 진행")
        build_packages(r, events=[])

    rebuild_site()
    log.info("%s 분석 입력 패키지 생성 완료", key)
    git_push_if_enabled(f"collect: {key} final package")


def git_push_if_enabled(message: str):
    from scheduler.config import load_config
    cfg = load_config()
    if not cfg.get("git", {}).get("auto_push", False):
        log.info("git auto_push 비활성 — 커밋 생략")
        return
    for cmd in (["git", "add", "data", "site"],
                ["git", "commit", "-m", message],
                ["git", "push"]):
        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if res.returncode != 0 and "nothing to commit" not in res.stdout + res.stderr:
            log.warning("git 실패 %s: %s", cmd, res.stderr.strip())
            return
    log.info("git push 완료: %s", message)
