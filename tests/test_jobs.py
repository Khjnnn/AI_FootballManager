"""스케줄러 잡 등록·감시 로직 테스트 (네트워크 없이 검증)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from collector.parse import parse_round
from scheduler import jobs

FIXTURES = Path(__file__).parent / "fixtures"
KST = timezone(timedelta(hours=9))


class FakeScheduler:
    def __init__(self):
        self.jobs = {}

    def add_job(self, func, trigger, run_date=None, args=None, id=None, **kw):
        self.jobs[id] = {"func": func, "run_date": run_date, "args": args}


@pytest.fixture
def round_2026_38():
    raw = json.loads((FIXTURES / "totoGameData_260038.json").read_text(encoding="utf-8"))
    return parse_round(raw)


def test_register_future_jobs(round_2026_38, monkeypatch):
    r = round_2026_38.model_copy(update={
        "analysis_due": datetime.now(KST) + timedelta(hours=5)})
    sched = FakeScheduler()
    jobs.register_round_jobs(sched, r)
    key = jobs.round_key(r)
    assert f"final-{key}" in sched.jobs
    assert f"watch-{key}" in sched.jobs
    # 감시 잡은 최종 수집 1시간 뒤 (= 마감−11h)
    assert (sched.jobs[f"watch-{key}"]["run_date"]
            - sched.jobs[f"final-{key}"]["run_date"]) == timedelta(hours=1)


def test_skip_past_jobs(round_2026_38):
    r = round_2026_38.model_copy(update={
        "analysis_due": datetime.now(KST) - timedelta(hours=13)})
    sched = FakeScheduler()
    jobs.register_round_jobs(sched, r)
    assert sched.jobs == {}  # 분석·감시 시점 모두 경과 → 미등록


def test_watch_report_alerts_when_missing(monkeypatch, tmp_path):
    alerts = []
    monkeypatch.setattr(jobs, "notify", lambda msg: alerts.append(msg))
    monkeypatch.setattr(jobs, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(jobs.subprocess, "run", lambda *a, **k: None)
    jobs.watch_report("2026-38")
    assert alerts and "2026-38" in alerts[0]


def test_watch_report_quiet_when_present(monkeypatch, tmp_path):
    alerts = []
    monkeypatch.setattr(jobs, "notify", lambda msg: alerts.append(msg))
    monkeypatch.setattr(jobs, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(jobs.subprocess, "run", lambda *a, **k: None)
    (tmp_path / "2026-38").mkdir()
    (tmp_path / "2026-38" / "M01.md").write_text("report", encoding="utf-8")
    jobs.watch_report("2026-38")
    assert alerts == []


def test_composition_change_alert(round_2026_38, monkeypatch, tmp_path):
    alerts = []
    monkeypatch.setattr(jobs, "notify", lambda msg: alerts.append(msg))
    prev_path = tmp_path / "2026-38.json"
    prev_path.write_text(round_2026_38.model_dump_json(), encoding="utf-8")
    changed = round_2026_38.model_copy(deep=True)
    changed.matches[0].home.betman_name = "다른팀"
    jobs.check_composition_change(prev_path, changed)
    assert alerts and "대진 구성 변경" in alerts[0]
