# CLAUDE.md — GEO CLI 멀티에이전트 시스템

---

## 1. 프로젝트 개요

이 프로젝트는 **GEO(Generative Engine Optimization) 분석을 자동화하는 멀티에이전트 CLI 시스템**이다.
브랜드의 AI 가시성을 측정하기 위해, 질문 생성 → AI 질의(웹 자동화) → 응답 수집 → 정량 분석 → 리포트 + 대시보드까지를 end-to-end로 수행한다.

**설계서**: `geo-cli-agent-design.md` — 모든 구현 판단의 1차 참조 문서. 설계서에 정의된 워크플로우, 데이터 스키마, 검증 기준을 반드시 따른다.

---

## 2. 핵심 원칙

### 2.1 작업 원칙

- **설계서 우선**: 구현 판단이 필요하면 `geo-cli-agent-design.md`를 먼저 확인한다. 설계서에 없는 판단이 필요하면 사용자에게 확인한다.
- **점진적 구현**: 한 번에 전체를 만들지 않는다. Phase 단위로 구현하고, 각 Phase가 동작 확인된 후 다음으로 넘어간다.
- **파일 기반 데이터 전달**: 에이전트 간 데이터는 `/output/` 하위 파일로 전달한다. 프롬프트 인라인은 작은 메타데이터에만 사용한다.
- **실패에 안전하게**: 모든 외부 호출(웹 자동화, API)은 실패를 전제로 설계한다. 재시도 → 폴백 → 스킵+로그 → 에스컬레이션 순서를 따른다.

### 2.2 코딩 원칙

- **언어**: Python 3.10+ (스크립트), TypeScript/React (대시보드)
- **타입 힌트**: 모든 함수에 타입 힌트를 명시한다
- **에러 핸들링**: bare `except` 금지. 구체적 예외를 잡고, 예상치 못한 에러는 로그 후 상위로 전파한다
- **로깅**: `print` 대신 `logging` 모듈 사용. 레벨: DEBUG(개발), INFO(진행상황), WARNING(재시도), ERROR(실패)
- **설정 분리**: 하드코딩 금지. API 키는 `config/api_keys.env`, 셀렉터는 `references/*.json`, 모델 설정은 `references/model_configs.json`
- **테스트 가능성**: 핵심 함수는 순수 함수로 작성. 외부 의존성(브라우저, API)은 주입 가능하게 설계

### 2.3 판단과 코드의 역할 분리

| 에이전트(LLM)가 직접 수행 | 스크립트로 처리 |
|--------------------------|----------------|
| 질문 생성, 자연스러움 판단 | 파일 I/O, JSON/CSV 파싱 |
| 브랜드 멘션/감성 분석 | API 호출, 웹 자동화 실행 |
| 품질 평가, 정성적 분석 | Rate limiting, 재시도 로직 |
| 리포트 서술, 인사이트 도출 | DOM 파싱, 데이터 변환 |
| 사용자 의도 파악 | 스키마 검증, 규칙 기반 체크 |

---

## 3. 워크플로우 총괄

```
Phase A: 의도 파악     → Orchestrator 직접    → analysis_brief.json
Phase B: 질문 생성     → Question Agent       → question_set.json
  [Human Review #1]
Phase C: AI 테스팅     → AI Testing Agent     → raw_responses/ + screenshots/
Phase D: 분석          → Analysis Agent       → CSV + JSON
  [Human Review #2]
Phase E-1: 리포트      → Report Agent         → .docx
Phase E-2: 대시보드    → Dashboard Agent      → .html
  [Human Review #3]
```

**Phase 실행 규칙:**
- Phase는 반드시 순서대로 실행한다 (A → B → C → D → E)
- E-1과 E-2는 병렬 실행 가능
- Human Review 시점에서 사용자 승인 없이 다음 Phase로 넘어가지 않는다
- 각 Phase 시작 시 이전 Phase의 산출물 존재 여부를 먼저 확인한다

---

## 4. 에이전트 매핑

### 서브에이전트

| 에이전트 | AGENT.md 경로 | 트리거 조건 | 참조 스킬 |
|----------|-------------|------------|----------|
| Question Agent | `/.claude/agents/question-agent/AGENT.md` | Phase A 완료 후 | question-generator, qa-checker |
| AI Testing Agent | `/.claude/agents/testing-agent/AGENT.md` | HR#1 승인 후 | ai-tester, qa-checker |
| Analysis Agent | `/.claude/agents/analysis-agent/AGENT.md` | Phase C 완료 후 | response-analyzer, qa-checker |
| Report Agent | `/.claude/agents/report-agent/AGENT.md` | HR#2 승인 후 | geo-report, qa-checker |
| Dashboard Agent | `/.claude/agents/dashboard-agent/AGENT.md` | HR#2 승인 후 | dashboard-builder, qa-checker |

### 호출 규칙

- **Orchestrator(이 파일)만** 서브에이전트를 호출한다
- 서브에이전트끼리 직접 호출하지 않는다
- 서브에이전트 호출 시 입력 파일 경로를 명시한다
- 서브에이전트 완료 후 산출물 경로를 확인한다

---

## 5. 스킬 매핑

| 스킬 | SKILL.md 경로 | 사용 에이전트 | 핵심 역할 |
|------|-------------|-------------|----------|
| question-generator | `/.claude/skills/question-generator/SKILL.md` | Question Agent | 질문 생성 규칙, 타입/페르소나 분류, 검색형 변환 |
| ai-tester | `/.claude/skills/ai-tester/SKILL.md` | AI Testing Agent | Playwright 웹 자동화, API 폴백, 세션/셀렉터 관리 |
| response-analyzer | `/.claude/skills/response-analyzer/SKILL.md` | Analysis Agent | LLM 응답 분석, CSV 스키마 변환, 정량 분석 |
| qa-checker | `/.claude/skills/qa-checker/SKILL.md` | 전체 공유 | 스키마/규칙/LLM 기반 검증 |
| dashboard-builder | `/.claude/skills/dashboard-builder/SKILL.md` | Dashboard Agent | React + Recharts 대시보드 생성 |
| geo-report | `/.claude/skills/geo-report/SKILL.md` | Report Agent | Word 리포트 생성 (기존 스킬) |

---

## 6. 데이터 플로우

### 6.1 파일 경로 규칙

```
/output/
├── analysis_brief.json                              ← Phase A 산출물
├── question_set.json                                ← Phase B 산출물
├── raw_responses/
│   ├── chatgpt_web/responses.json                   ← Phase C 산출물
│   ├── google_ai_overview/responses.json            ← Phase C 산출물
│   └── openai_api_fallback/responses.json           ← Phase C 폴백
├── screenshots/
│   ├── chatgpt/*.png                                ← Phase C 에비던스
│   └── google_aio/*.png                             ← Phase C 에비던스
├── geo_analysis_{model}_{brand}_{date}.csv          ← Phase D 산출물
├── geo_analysis_combined_{brand}_{date}.csv         ← Phase D 산출물
├── analysis_{model}.json                            ← Phase D 산출물
├── GEO_분석_리포트_{brand}_{model}_{date}.docx       ← Phase E-1 산출물
├── dashboard/index.html                             ← Phase E-2 산출물
└── logs/execution_log.json                          ← 전 Phase 로그
```

### 6.2 Phase 간 전달

| From → To | 전달 파일 | 비고 |
|-----------|----------|------|
| A → B | `analysis_brief.json` | 필수 필드 스키마 검증 후 전달 |
| B → C | `question_set.json` | HR#1 승인 반영 완료본 |
| C → D | `raw_responses/*/responses.json` | 모델별 분리 저장 |
| D → E-1 | CSV + JSON | analyze_csv.py 출력 |
| D → E-2 | CSV + JSON | 동일 데이터, 병렬 전달 |

---

## 7. 웹 자동화 전략

### 7.1 우선순위

```
1순위: 웹 자동화 (Playwright)  ← 실제 소비자 경험과 동일, 비용 절감
2순위: API 폴백              ← 웹 실패 시에만 (ChatGPT만 해당)
```

### 7.2 타겟 모델 (Phase 1)

| 타겟 | 방식 | 폴백 |
|------|------|------|
| ChatGPT 웹 | Playwright (chat.openai.com) | OpenAI API |
| Google AI Overview | Playwright (google.com/search) | 없음 (스킵+로그) |

### 7.3 세션 관리

- ChatGPT: `config/chatgpt_cookies.json` → Playwright Context에 쿠키 로드
- 매 실행 전 세션 유효성 체크 (프로필 버튼 존재 여부)
- 세션 만료 시: 즉시 중단 → HR#긴급 발동 → 사용자가 쿠키 재제공 또는 API 전환 결정

### 7.4 셀렉터 유지보수

- 셀렉터는 스크립트 코드에 하드코딩하지 않는다
- `references/chatgpt_selectors.json`, `references/google_aio_selectors.json`에서 로드
- 셀렉터 실패 감지 시:
  1. 로그에 실패 셀렉터와 대상 URL 기록
  2. 사용자에게 셀렉터 업데이트 필요 알림
  3. 가능하면 LLM이 페이지 소스를 분석하여 대체 셀렉터 제안

### 7.5 봇 감지 방지

- 질문 간 랜덤 딜레이: ChatGPT 8~15초, Google 5~10초
- User-Agent 로테이션 (Google)
- 마우스 움직임 시뮬레이션 (선택)
- CAPTCHA 감지 시 즉시 일시 정지 → Human 에스컬레이션

---

## 8. Human Review 프로토콜

| 시점 | 제시할 내용 | 사용자 선택지 | 미응답 시 |
|------|-----------|-------------|----------|
| **HR#1** (질문 확인) | 질문 목록 요약 + 분포표 + 검색형 변환 샘플 | 승인 / 수정 / 재생성 | 승인 처리 |
| **HR#2** (분석 확인) | KPI 요약 (Visibility, SoV, Sentiment) + 모델 비교 + AIO 커버리지 | 승인 / 추가 분석 / 중단 | 승인 처리 |
| **HR#3** (최종 확인) | 리포트 파일 + 대시보드 링크 | 승인 / 수정 지시 | **반드시 응답 대기** |
| **HR#긴급** (세션 만료) | "ChatGPT 세션이 만료됨. 조치 필요" | 쿠키 재제공 / API 전환 / 중단 | **반드시 응답 대기** |

**제시 형식:**
- 요약은 간결하게 (핵심 수치 + 이상치만 하이라이트)
- 수정이 필요할 가능성이 높은 항목을 먼저 제시
- "문제 없으면 승인해주세요"로 마무리

---

## 9. 실패 처리 총괄

### 9.1 패턴

| 패턴 | 사용 시점 | 최대 횟수 |
|------|----------|----------|
| **자동 재시도** | 형식 오류, 일시적 네트워크 실패, DOM 로딩 지연 | 2회 |
| **폴백** | ChatGPT 웹 → OpenAI API (채널 전환) | 1회 |
| **스킵 + 로그** | 선택적 데이터 (개별 질문 실패, AIO 미표시) | — |
| **에스컬레이션** | 세션 만료, CAPTCHA, 전체 채널 장애, 판단 불확실 | — |

### 9.2 에이전트별 실패 처리

| 에이전트 | 주요 실패 시나리오 | 처리 |
|----------|------------------|------|
| Question Agent | 분포 불균형, 중복 과다 | 재생성 1회 → HR |
| AI Testing Agent | 세션 만료 | HR#긴급 (즉시) |
| AI Testing Agent | 개별 질문 웹 실패 | 재시도 1회 → API 폴백 → 스킵 |
| AI Testing Agent | 봇 감지/차단 | 전체 API 폴백 전환 → HR |
| Analysis Agent | CSV 스키마 불일치 | 재변환 1회 → HR |
| Analysis Agent | 멘션 정확도 미달 | 전체 재분석 1회 → HR |
| Report Agent | docx 생성 실패 | 재생성 1회 → HR |
| Dashboard Agent | React 렌더링 에러 | 재생성 1회 → HR |

---

## 10. 실행 로그 규칙

모든 Phase의 시작/종료/실패를 `/output/logs/execution_log.json`에 기록한다.

```json
{
  "execution_id": "geo_20250319_143022",
  "started_at": "2025-03-19T14:30:22",
  "brand": "Samsung",
  "phases": [
    {
      "phase": "A",
      "status": "completed",
      "started_at": "...",
      "completed_at": "...",
      "output_file": "analysis_brief.json"
    },
    {
      "phase": "C",
      "status": "completed_with_fallback",
      "details": {
        "chatgpt_web": {"success": 76, "api_fallback": 3, "skipped": 1},
        "google_aio": {"success": 62, "no_overview": 18}
      }
    }
  ],
  "errors": [
    {
      "phase": "C",
      "timestamp": "...",
      "type": "session_expired",
      "message": "ChatGPT 쿠키 만료 감지",
      "resolution": "user_provided_new_cookies"
    }
  ]
}
```

**기록 시점:**
- Phase 시작/종료
- Human Review 요청/응답
- 재시도/폴백 발생
- 에러 및 에스컬레이션
- 최종 산출물 파일 경로

---

## 11. 구현 순서 가이드

Claude Code에서 이 프로젝트를 구현할 때 아래 순서를 따른다:

### Step 1: 프로젝트 스캐폴딩
- 폴더 구조 생성 (`/.claude/skills/`, `/.claude/agents/`, `/output/`, `/config/`)
- 빈 AGENT.md, SKILL.md 파일 배치
- `config/api_keys.env.example` 생성

### Step 2: AI Testing Agent (가장 복잡, 먼저 검증)
- `session_manager.py` → 쿠키 로드/세션 체크
- `chatgpt_automator.py` → 단일 질문 테스트부터 시작
- `google_aio_automator.py` → 단일 검색 테스트
- `api_caller.py` → 폴백 경로
- `response_parser.py` → 통일 스키마 정규화
- **검증**: 5개 질문으로 전체 파이프라인 테스트

### Step 3: Question Agent
- `question-generator` 스킬 작성
- 질문 생성 로직 (대화형 + 검색형)
- QA 검증 (분포, 중복, 자연스러움)

### Step 4: Analysis Agent
- `csv_builder.py` → raw_responses → CSV 변환
- `analyze_csv.py` 연동 테스트
- LLM 분석 프롬프트 고정 (temperature 0)

### Step 5: Report Agent + Dashboard Agent
- geo-report 스킬 연동
- React + Recharts 대시보드 템플릿 생성

### Step 6: Orchestrator 통합
- Phase 간 연결
- Human Review 흐름
- 실행 로그
- 전체 end-to-end 테스트

---

## 12. 자주 참조하는 경로

| 용도 | 경로 |
|------|------|
| 설계서 | `geo-cli-agent-design.md` |
| ChatGPT 셀렉터 | `/.claude/skills/ai-tester/references/chatgpt_selectors.json` |
| Google AIO 셀렉터 | `/.claude/skills/ai-tester/references/google_aio_selectors.json` |
| API 설정 | `/.claude/skills/ai-tester/references/model_configs.json` |
| CSV 스키마 정의 | `/.claude/skills/response-analyzer/references/csv_schema.md` |
| 리포트 구조 | `/.claude/skills/geo-report/references/report_structure.md` |
| 쿠키 파일 | `config/chatgpt_cookies.json` |
| API 키 | `config/api_keys.env` |
| 실행 로그 | `/output/logs/execution_log.json` |

---

## 13. 금지 사항

- `/config/` 하위 파일(API 키, 쿠키)을 절대 git에 커밋하지 않는다
- 셀렉터를 스크립트 코드에 하드코딩하지 않는다 (반드시 JSON에서 로드)
- 사용자 확인 없이 Human Review를 건너뛰지 않는다 (HR#3, HR#긴급은 반드시 대기)
- analyze_csv.py의 출력 수치를 LLM이 추정하거나 변형하지 않는다 (있는 그대로 사용)
- 웹 자동화 시 질문 간 딜레이를 5초 미만으로 설정하지 않는다

