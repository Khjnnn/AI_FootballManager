# 배트맨 수집 PoC 결과 (1주차)

**작성일:** 2026-07-09
**검증 대상:** 2026년 38회차 (gmTs=260038), 실데이터 14경기 파싱 성공
**산출물:** `poc/capture_betman.py`(캡처), `poc/parse_round.py`(파서), `data/rounds/2026-38.json`(실데이터)

## 1. 확정된 JSON 엔드포인트

모두 `POST`, `Content-Type: application/json`. 세션·인증 헤더 없이 동작 확인(2026-07-09 기준).

| 용도 | 엔드포인트 | 요청 본문 |
|---|---|---|
| **회차 감지** (발매 중 게임 목록) | `POST /buyPsblGame/inqBuyAbleGameInfoList.do` | `{"_sbmInfo":{"_sbmInfo":{"debugMode":"false"}}}` |
| **회차 상세** (14경기 + 투표 분포) | `POST /buyPsblGame/totoGameData.do` | `{"gmId":"G011","gmTs":260038,"_sbmInfo":{"_sbmInfo":{"debugMode":"false"}}}` |
| 회차 상세 (동일 응답) | `POST /buyPsblGame/gameInfoInq.do` | 위와 동일 — totoGameData.do의 폴백으로 사용 가능 |

- Base URL: `https://www.betman.co.kr`
- `_sbmInfo` 래퍼는 모든 요청에 공통으로 붙는 프레임워크 파라미터.
- 회차 감지: `totoGames[]`에서 `gameMaster.gmId == "G011"` 항목의 `gmTs`를 읽는다.

## 2. 응답 스키마 요점 (totoGameData.do)

| 경로 | 내용 |
|---|---|
| `currentLottery.gmTs` | 회차 ID (260038) |
| `currentLottery.gmOsidTsYear` / `gmOsidTs` | 연도(2026) / 회차 번호(38) — **gmTs = 연도 2자리 + 회차 4자리 패딩 규칙 확인됨** |
| `currentLottery.saleStartDate` / `saleEndDate` | 발매 시작/마감 (epoch ms, KST 변환 필요) |
| `schedulesList[]` (14개) | 경기별: `matchSeq`, `leagueName`, `homeName/awayName`, `homeId/awayId`, `gameDate`(epoch ms), `meetStadium`, `handi`, `domastic` |
| `voteStatus.homeVoteStatusList[]` (14개) | 경기별 `awayVoteStatusList[]` 3개 = **승/무/패 투표 수** |
| `standardDate` | 응답 기준 시각 (epoch ms) |

## 3. 핵심 발견: 승무패에는 고정 배당이 없다

`schedulesList[].winAllot/drawAllot/loseAllot`은 전부 `0.0`이다. 승무패(G011)는 프로토(승부식)와 달리 **패리뮤추얼(투표 총액 분배) 방식**이라 배트맨 자체 고정 배당이 존재하지 않는다.

**plan.md에 미치는 영향:**
- "배트맨 배당 vs 해외 배당 괴리" 지표(2.2절, 7.2절 분석 프롬프트 4번 항목)는 **"대중 투표 분포 vs 해외 시장 내재확률 괴리"로 대체**해야 한다.
- 투표 분포는 오히려 유용한 신호다: 대중 쏠림(예: M04 수원삼성 원정승 85%)과 시장 확률의 차이가 곧 이변 후보 탐지 지표가 된다.
- 데이터 모델(6절)의 `betman_odds` 필드는 `vote_counts`/`vote_dist`로 교체됨 — `parse_round.py`에 이미 반영.

## 4. 접근성 확인

- Playwright headless Chromium + 일반 UA로 차단 없이 접근됨 (robots 정책상 저빈도 원칙은 유지).
- 페이지 렌더링 없이 **엔드포인트 직접 POST 호출(방식 A)로 전환 가능**할 것으로 보이나, 쿠키/세션 필요 여부는 2주차에 httpx 직접 호출로 검증 필요.
- 요청 2회(목록 + 상세)로 회차 전체 정보 수집 완료 — 회차당 요청 예산 내 충분.

## 5. 다음 단계 (2주차 진입 조건)

1. httpx로 두 엔드포인트 직접 호출 검증 (세션 불필요 여부) → 방식 A 확정
2. `parse_round.py`를 `collector/` 모듈로 승격 + pydantic 스키마(6.1절)
3. 회차 감지 데몬 + APScheduler (5절)
4. plan.md 갱신: 배트맨 배당 → 투표 분포 대체 반영

## 미해결 항목

- zentoto 벤치마크 분석(`docs/benchmark-zentoto.md`)은 브라우저 수동 분석이 필요해 별도 진행 (plan 2.2절).
- 회차 종료 후 결과 조회 엔드포인트는 미탐색 (7.4절 결과 수집 시 필요 — 3~4주차).
