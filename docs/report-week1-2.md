# 배트맨 승무패 AI 분석 시스템 — 1~2주차 PDCA 완료 보고서

**프로젝트:** ai_football_manager
**작성일:** 2026-07-09 (로드맵상 1~2주차 범위를 당일 압축 수행)
**상태:** ✅ 수집 PoC + 자동화 골격 완성, 테스트 14/14 통과

---

## 1. PDCA 사이클 요약

### Plan — plan.md v1.0 → v1.3

| 버전 | 주요 변경 | 계기 |
|---|---|---|
| v1.0 | 초안 (수집→스케줄→AI 분석→리포트 골격) | 착수 |
| v1.1 | 실행 빈틈 8건 보강 (로컬 트리거·데이터 소스·예외 처리·시크릿·프로젝트 구조·테스트 전략 등) | 문서 검토 |
| v1.2 | 사용자 구상 반영: **Claude CLI 기본**, **Cloudflare Pages 정적 배포**, 회차 페이지 라이프사이클(①예정→②분석→③결과) | 구상-문서 대조 검증 |
| v1.3 | PoC 발견 반영: 엔드포인트 확정, gmTs 규칙 확증, **고정 배당 부재 → 투표 분포 대체** | 1주차 PoC |

### Do — 1주차: 수집 PoC (`docs/poc-betman.md`)

- 배트맨 JSON 엔드포인트 3개 역공학 확정: `inqBuyAbleGameInfoList.do`(감지), `totoGameData.do`(상세), `gameInfoInq.do`(폴백)
- `gmTs=260038` = 2026년 38회차 규칙 확증 (`gmOsidTsYear`/`gmOsidTs`)
- **핵심 발견: 승무패는 패리뮤추얼 방식 — 고정 배당이 없다.** 대신 경기별 승/무/패 투표 수 제공 → 대중 투표 분포를 대체 신호로 채택
- 실데이터 파싱 성공: `data/rounds/2026-38.json` (14경기, KST 시각, 투표 분포)
- httpx 직접 호출(방식 A) 라이브 검증: 세션 쿠키 없이 200 + 14경기 수신

### Do — 2주차: 자동화 골격

| 모듈 | 내용 |
|---|---|
| `collector/` | pydantic 스키마(14경기·분포 합=1 검증), httpx 기본 + Playwright 자동 폴백, 상태 매핑(취소/연기→적특) |
| `scheduler/` | 매일 09:00 KST 감지 데몬, 마감−12h 최종 수집 잡 + 마감−11h 미완료 감시 잡 동적 등록, 재시작 시 회차 파일에서 잡 복원, 구성 변경 경보, notify 스텁 |
| `site_builder/` | 7.5절 ① 예정 페이지 + 아카이브 인덱스, design_teq.md 토큰 준수, 데스크톱·모바일(390px) 스크린샷 검증 |
| `scripts/` | `local_poll.ps1` 로컬 폴링 트리거 (analyzer는 3주차 연결) |
| 설정 | `config/config.yaml`, `.env.example`(키 3종 — Claude는 CLI 세션이라 키 불필요), `requirements.txt` |
| `tests/` | 실응답 픽스처 + FakeScheduler, 14개 테스트 |

### Check — gap-detector 갭 분석

- **Match Rate 85%** (2주차 범위), design_teq.md 체크리스트 95% 준수, 테스트 100%
- 지적 4건: ① APScheduler 잡 영속화 문서-구현 불일치 ② 마감−11h 감시 잡 누락 ③ 경기 취소·연기 상태 매핑 누락 ④ 회차 구성 변경 경고 누락

### Act — 개선 4건 적용 → 90% 이상

1. plan.md 5·8절을 실제 구현("회차 파일 기반 잡 복원")과 동기화
2. `watch_report` 감시 잡 + `scheduler/notify.py` 경보 스텁 추가
3. `parse_round` 상태 매핑(`gameReject/buyReject→cancelled`, `unsetSchedule→postponed`) — 사이트 "적특 예상" 표기와 연결
4. `check_composition_change` 대진·마감시각 diff 경보

테스트 8개 → **14개 확장, 전부 통과.**

---

## 2. 교훈 (Lessons Learned)

1. **가정은 실데이터로 조기 검증하라.** "배트맨 배당 존재" 가정이 PoC 첫날 뒤집혔다(패리뮤추얼). 1주차에 발견해 재설계 비용이 문서 수정 수준에 그쳤다 — 3주차에 발견했다면 분석 프롬프트·데이터 모델·화면까지 연쇄 리팩토링이었다.
2. **pydantic 검증을 단일 관문으로.** 스키마 검증 실패가 폴백·경보를 트리거하는 구조라 사이트 개편 감지가 한곳에 모인다.
3. **잡 영속화는 데이터 파일로 충분했다.** 모든 동적 잡이 회차 파일에서 파생되므로 DB 없이 재시작 복원이 된다. 단, 회차 파생이 아닌 잡이 늘면 SQLite 잡스토어로 전환(plan 5절에 조건 명시).
4. **환경 호환성 조기 확인.** httpx 0.27이 Python 3.14에서 임포트 불가 — 첫 실행에서 잡아 업그레이드로 해결.
5. **갭 분석은 구현 직후가 효과적.** 문서-구현 불일치 4건을 코드가 식기 전에 교정했다.

---

## 3. 미결 항목

**사용자 외부 작업 (3주차 전 필요):**
- [ ] 프라이빗 Git 원격 저장소 생성 + 첫 커밋·푸시
- [ ] Cloudflare Pages 연동 (빌드 명령 없음, 출력 디렉터리 `site`, Access로 본인 이메일만 허용)
- [ ] API 키 2종 발급: The Odds API(the-odds-api.com), API-Football(dashboard.api-football.com) → `.env`
- [ ] VPS에 `python -m scheduler.daemon` 상주, 로컬 PC에 `scripts/local_poll.ps1` 작업 스케줄러 등록

**개발 (3주차):** 부가 데이터 수집기(해외배당·폼·전적·결장자), `config/teams.yaml` 팀명 매핑, `analyzer/` Claude CLI 분석기 + 프롬프트 v1, 경기별 리포트 → 사이트 라이프사이클 ②

**병렬 진행:** zentoto 벤치마크 수동 분석(`docs/benchmark-zentoto.md`)

**보류(낮음):** 웹폰트 CDN 링크, gmTs 선제 조회 보조 로직

---

## 4. 성과 지표

| 지표 | 목표 | 달성 |
|---|---|---|
| 설계-구현 일치도 | ≥90% | 85% → 개선 후 **90%+** |
| 테스트 통과율 | 100% | **14/14** |
| design_teq 체크리스트 | 준수 | **95%** (신뢰도 배지는 ② 단계 항목) |
| 실데이터 수집 | 회차 1개 | **2026-38회차 완료** |
