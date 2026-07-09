"""캐시된 배당으로 2026-38 입력 패키지 생성 (API 호출 없음)."""
import json
import logging
from pathlib import Path

from collector.enrich import build_packages
from collector.models import Round

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
ROOT = Path(__file__).parent.parent

r = Round.model_validate_json(
    (ROOT / "data" / "rounds" / "2026-38.json").read_text(encoding="utf-8"))
events = []
for f in ("odds_soccer_korea_kleague1.json", "odds_soccer_norway_eliteserien.json"):
    events.extend(json.loads((ROOT / "data" / "cache" / f).read_text(encoding="utf-8")))

pkg_dir = build_packages(r, events)
sample = json.loads((pkg_dir / "M01.json").read_text(encoding="utf-8"))
print(json.dumps(sample, ensure_ascii=False, indent=1))
