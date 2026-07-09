"""수집 스케줄러 데몬 (서버 상주 프로세스).

- 매일 09:00 KST 회차 감지 (config.yaml에서 변경 가능)
- 시작 시 즉시 1회 감지 + 저장된 회차의 미래 최종 수집 잡 재등록
  (메모리 잡스토어를 쓰는 대신, 재시작 시 data/rounds/*.json에서 복원)

실행: python -m scheduler.daemon
"""
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from scheduler.config import load_config
from scheduler.jobs import detect_and_register, load_saved_rounds, register_round_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("daemon")


def main():
    cfg = load_config()
    detect_time = str(cfg.get("detect", {}).get("time", "09:00"))
    hour, minute = (int(x) for x in detect_time.split(":"))

    sched = BlockingScheduler(timezone="Asia/Seoul")
    sched.add_job(detect_and_register, "cron", hour=hour, minute=minute,
                  args=[sched], id="detect-daily")

    # 재시작 복원: 저장된 회차에서 미래의 최종 수집·감시 잡을 재등록
    for r in load_saved_rounds():
        register_round_jobs(sched, r)

    log.info("시작: 매일 %02d:%02d KST 감지, 즉시 1회 실행", hour, minute)
    detect_and_register(sched)
    sched.start()


if __name__ == "__main__":
    main()
