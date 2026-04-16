# GEO CLI 멀티에이전트 시스템 설계서

> 버전: v1.1
> 작성일: 2025-03-19
> 최종 수정: 2025-03-19 (웹 자동화 우선 방향으로 전면 재설계)
> 용도: Claude Code 구현 참조용 계획서

---

## 1. 작업 컨텍스트

### 1.1 배경

GEO(Generative Engine Optimization)는 생성형 AI(ChatGPT, Gemini, Perplexity 등)가 특정 브랜드를 얼마나 잘 인지하고, 어떤 맥락에서, 어떤 톤으로 언급하는지를 분석하는 분야다. 현재는 CSV 데이터가 이미 준비된 상태에서 분석 → 리포트를 생성하는 스킬(`geo-report`)이 존재하지만, **질문 설계 → AI 질의 → 응답 수집 → CSV 구조화**까지의 상류(upstream) 파이프라인은 수동으로 수행되고 있다.

이 시스템은 상류 파이프라인 전체를 자동화하고, 기존 geo-report 스킬과 연결하여 **end-to-end GEO 분석 파이프라인**을 구축한다.

### 1.2 목적

자연어 CLI 인터페이스를 통해 브랜드의 AI 가시성(AI Visibility)을 체계적으로 측정·분석하는 멀티에이전트 시스템. 사용자가 브랜드명과 분석 관점을 제공하면, 시스템이 질문 생성 → AI 질의 → 응답 수집 → 정량/정성 분석 → 리포트 + 대시보드까지 자동으로 수행한다.

### 1.3 범위

**In-Scope (Phase 1 — MVP):**
- 사용자 의도 파악을 위한 대화형 인터뷰 (Orchestrator)
- 타겟 고객 관점의 자연스러운 질문 생성
- **웹 자동화 기반 AI 질의 (Playwright)**
  - ChatGPT 웹 (chat.openai.com) — 실제 소비자와 동일한 응답 수집
  - Google 검색 AI Overview — 검색 결과 내 AI 스니펫 수집
- OpenAI API 폴백 (웹 자동화 실패 시 대체 경로)
- 응답 데이터의 정량 분석 (Visibility, SoV, Sentiment, Rank 등)
- 기존 geo-report 스킬 연동을 통한 Word 리포트 생성
- 인터랙티브 React + Recharts 대시보드 생성
- Human-in-the-loop 검토 지점
- QA 스킬에 의한 품질 검증

**Out-of-Scope (Phase 2 — 확장):**
- 추가 웹 자동화 타겟 (Perplexity 웹, Gemini 웹)
- 추가 API 타겟 (Gemini API, Perplexity API)
- 월별 자동 스케줄링 / 크론 실행
- 멀티 브랜드 동시 비교 분석
- 자체 DB 서버 운영 (로컬 SQLite/JSON 기반)

### 1.4 웹 자동화 우선 전략 근거

| 근거 | 설명 |
|------|------|
| **실제 소비자 경험과 동일** | API 응답과 웹 UI 응답은 다를 수 있음. GEO는 소비자가 실제로 보는 답변을 분석해야 의미 있음 |
| **비용 효율** | 웹 UI는 무료 티어 활용 가능. API는 50~100개 질문 × 토큰 비용 발생 |
| **Google AI Overview** | API가 존재하지 않음. 웹 자동화만이 유일한 수집 경로 |

**폴백 전략:**
- ChatGPT 웹 자동화 실패 (로그인 차단, CAPTCHA, DOM 변경) → OpenAI API로 전환
- Google AI Overview 자동화 실패 → 해당 모델 스킵 + 로그 기록 (API 대체 불가)

### 1.5 입출력 정의

**입력:**
- 사용자의 자연어 명령 (예: "삼성 TV의 AI 기능에 대한 GEO 분석 해줘")
- (선택) 기존 질문 리스트 시드 파일
- (선택) 이전 분석 Baseline JSON
- (필수) ChatGPT 로그인 세션 쿠키 또는 인증 정보

**최종 산출물:**
| 산출물 | 형식 | 설명 |
|--------|------|------|
| 질문 리스트 | JSON | 카테고리/타입/페르소나별 구조화된 질문 세트 |
| AI 응답 원본 | JSON | 모델별 원본 응답 + 스크린샷 에비던스 |
| 분석 데이터 | CSV | geo-report 스킬 입력 스키마 호환 |
| 분석 결과 | JSON | analyze_csv.py 출력 (정량 지표) |
| 컨설팅 리포트 | .docx | geo-report 스킬 산출물 |
| 인터랙티브 대시보드 | .html (React + Recharts) | 필터/드릴다운 가능한 웹앱 |
| 실행 로그 | JSON | 각 단계별 성공/실패/스킵 기록 |
| 스크린샷 아카이브 | PNG | 웹 자동화 에비던스 (질문별 응답 화면 캡처) |

### 1.6 주요 제약조건

- **CSV 스키마 호환**: 분석 에이전트의 산출 CSV는 기존 `analyze_csv.py`의 필수 컬럼과 정확히 일치해야 함
- **웹 자동화 안정성**: ChatGPT/Google의 DOM 구조 변경에 취약 → 셀렉터 관리 전략 필요
- **세션 관리**: ChatGPT 웹은 로그인 필요 → 쿠키/토큰 기반 세션 유지
- **요청 간 딜레이**: 봇 감지 방지를 위한 자연스러운 간격 유지 (5~15초/질문)
- **질문 자연스러움**: 생성된 질문이 "테스트용"으로 보이지 않아야 함
- **데이터 무결성**: AI 응답 원본은 변형 없이 보존 + 스크린샷 에비던스 첨부

### 1.7 용어 정의

| 용어 | 정의 |
|------|------|
| AI Visibility | 타겟 브랜드가 AI 응답에서 한 번이라도 언급된 비율 |
| SoV (Share of Voice) | 전체 브랜드 멘션 중 타겟 브랜드 멘션 비율 |
| Sentiment | AI가 브랜드를 언급할 때의 감성 (긍정/중립/부정) |
| Rank / Position | 브랜드가 응답 내에서 언급되는 순서 (1=최초 언급) |
| Persona | 질문을 할 것으로 예상되는 사용자 유형 |
| Framing | AI가 브랜드를 언급하는 맥락 (primary/compared/listed/absent) |
| Reference | AI가 답변 근거로 인용한 출처 URL |
| Target Model | 질문을 전송할 대상 AI 서비스 |
| AI Overview | Google 검색 결과 상단에 표시되는 AI 생성 요약 스니펫 |
| DOM Selector | 웹 페이지 요소를 식별하기 위한 CSS/XPath 경로 |

---

## 2. 워크플로우 정의

### 2.1 전체 흐름 개요

```
사용자 명령
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  ORCHESTRATOR (메인 에이전트)                              │
│  "전체 워크플로우 감독, 에이전트 조율, Human-in-Loop 관리"    │
└─────────┬───────────────────────────────────────────────┘
          │
          │ Phase A: 의도 파악
          ▼
    ┌─────────────┐
    │ Orchestrator │──▶ 사용자 인터뷰 (2~3턴)
    │ 직접 수행     │◀── 브랜드, 카테고리, 분석 관점, 규모 확정
    └──────┬──────┘
           │
           │ Phase B: 질문 생성
           ▼
    ┌─────────────────┐      ┌───────────┐
    │ Question Agent   │──▶──│ QA 스킬   │──▶ [Human Review #1]
    │ 질문 세트 생성    │◀──◀─│ 질문 검증   │     질문 리스트 확인
    └──────┬──────────┘      └───────────┘
           │
           │ Phase C: AI 테스팅 (웹 자동화)
           ▼
    ┌──────────────────────┐      ┌───────────┐
    │ AI Testing Agent      │──▶──│ QA 스킬   │
    │ ┌──────────────────┐ │◀──◀─│ 응답 검증   │
    │ │ ChatGPT 웹 (1순위)│ │      └───────────┘
    │ │ → OpenAI API 폴백 │ │
    │ ├──────────────────┤ │
    │ │ Google AI Overview│ │
    │ │ (웹 전용)         │ │
    │ └──────────────────┘ │
    └──────┬───────────────┘
           │
           │ Phase D: 데이터 구조화 + 분석
           ▼
    ┌──────────────────┐      ┌───────────┐
    │ Analysis Agent    │──▶──│ QA 스킬   │──▶ [Human Review #2]
    │ CSV 생성 + 정량분석│◀──◀─│ 데이터 검증 │     분석 결과 확인
    └──────┬───────────┘      └───────────┘
           │
           │ Phase E: 리포트 + 대시보드
           ├──────────────────────┐
           ▼                      ▼
    ┌──────────────┐      ┌──────────────────┐
    │ Report Agent  │      │ Dashboard Agent   │
    │ Word 리포트   │      │ React 대시보드     │
    └──────┬───────┘      └──────┬───────────┘
           │                      │
           └──────────┬───────────┘
                      ▼
              [Human Review #3]
              최종 산출물 검토
```

### 2.2 Phase A: 의도 파악 (Orchestrator 직접 수행)

| 항목 | 내용 |
|------|------|
| **수행 주체** | Orchestrator (LLM 판단) |
| **트리거** | 사용자의 최초 명령 |
| **목표** | 분석 스코프를 확정하여 `analysis_brief.json` 생성 |

**Orchestrator가 파악해야 할 항목:**

```
analysis_brief.json
{
  "brand": "Samsung",
  "industry": "Consumer Electronics",
  "categories": ["TV", "Smartphone", "Home Appliance"],
  "analysis_angles": ["AI 기능 인지도", "가격 경쟁력", "브랜드 포지셔닝"],
  "target_models": [
    {
      "name": "chatgpt_web",
      "type": "web",
      "priority": 1,
      "fallback": "openai_api"
    },
    {
      "name": "google_ai_overview",
      "type": "web",
      "priority": 2,
      "fallback": null
    }
  ],
  "question_scale": 80,
  "personas": ["얼리어답터", "가성비 추구형", "전문가형"],
  "language": "ko",
  "seed_questions": null,
  "baseline_path": null
}
```

**입력 수준별 처리 (유연한 지원):**

| 사용자 입력 수준 | Orchestrator 행동 |
|-----------------|------------------|
| 브랜드명만 ("삼성 TV") | 산업/카테고리 추론 → 분석 관점 제안 → 확인 |
| 브랜드 + 구체적 관점 ("삼성 TV AI 기능 인지도, 가격 경쟁력") | 규모/페르소나만 추가 확인 |
| 기존 질문 시드 파일 제공 | 시드 분석 → 빈 영역 보충 질문 생성으로 전환 |
| 모두 상세 입력 | 바로 Phase B 진행 |

| 검증 | 내용 |
|------|------|
| **성공 기준** | `analysis_brief.json`의 필수 필드가 모두 채워져 있음 |
| **검증 방법** | 스키마 검증 (필수 필드 존재 + 타입) |
| **실패 시 처리** | 에스컬레이션 → 사용자에게 부족 항목 재질문 (최대 3턴) |

---

### 2.3 Phase B: 질문 생성 (Question Agent)

| 항목 | 내용 |
|------|------|
| **수행 주체** | Question Agent (LLM 판단) |
| **입력** | `analysis_brief.json` |
| **출력** | `question_set.json` |

**질문 생성 원칙:**
- 실제 타겟 고객이 자연스럽게 할 법한 질문이어야 함
- "~의 장단점은?" 같은 직접적 질문 + "~를 선택할 때 고려할 점은?" 같은 간접적 질문 혼합
- 브랜드명을 직접 언급하는 질문과 언급하지 않는 질문(카테고리만)을 모두 포함
- 각 질문에 카테고리, 타입, 페르소나, 태그를 메타데이터로 부여
- **Google AI Overview용 질문은 검색 쿼리 형태로 별도 생성** (대화형이 아닌 검색형)

**질문 타입 분류:**

| 타입 | 설명 | 예시 (대화형) | 예시 (검색형 — AI Overview) |
|------|------|--------------|--------------------------|
| branded_direct | 브랜드명 직접 포함 | "삼성 TV의 AI 기능은 뭐가 있어?" | "삼성 TV AI 기능" |
| branded_comparative | 브랜드 간 비교 | "삼성 TV vs LG TV 뭐가 더 나아?" | "삼성 TV vs LG TV 비교" |
| category_generic | 카테고리만 언급 | "65인치 TV 추천해줘" | "65인치 TV 추천 2025" |
| feature_specific | 특정 기능 중심 | "AI 업스케일링 가장 잘하는 TV는?" | "AI 업스케일링 TV 순위" |
| purchase_intent | 구매 의도 | "100만원대 TV 뭐가 가성비 좋아?" | "100만원 TV 가성비 추천" |
| problem_solving | 문제 해결 | "TV 화질이 좋으려면 뭘 봐야 해?" | "TV 화질 좋은 기준" |

**질문 세트 구조:**

```
question_set.json
{
  "metadata": {
    "brand": "Samsung",
    "total_questions": 80,
    "generated_at": "2025-03-19T...",
    "distribution": {
      "by_category": {"TV": 30, "Smartphone": 30, "Home Appliance": 20},
      "by_type": {"branded_direct": 15, "branded_comparative": 15, ...},
      "by_persona": {"얼리어답터": 20, "가성비 추구형": 25, ...}
    }
  },
  "questions": [
    {
      "id": "q0001",
      "text_conversational": "65인치 TV 추천해줘. AI 기능이 좋은 걸로.",
      "text_search": "65인치 TV AI 기능 추천 2025",
      "category": "TV",
      "type": "category_generic",
      "persona": "얼리어답터/기술 탐색형",
      "tags": ["TV", "AI 기능", "추천"],
      "language": "ko",
      "brand_mentioned": false
    },
    ...
  ]
}
```

**QA 스킬 검증 (질문 품질):**

| 검증 항목 | 기준 | 방법 |
|-----------|------|------|
| 자연스러움 | 테스트 티가 나지 않는가 | LLM 자기 검증 |
| 분포 균형 | 카테고리/타입/페르소나 편향 없는가 | 규칙 기반 (분포 비율 체크) |
| 중복 | 의미적으로 중복되는 질문이 없는가 | LLM 유사도 판단 |
| 커버리지 | analysis_brief의 분석 관점이 모두 반영되었는가 | 규칙 기반 (관점별 최소 N개) |
| 검색형 변환 | 검색 쿼리가 자연스러운가 (조사/어미 제거) | LLM 자기 검증 |

| 검증 | 내용 |
|------|------|
| **성공 기준** | 질문 수 ≥ 목표의 90%, 분포 편차 ≤ 20%, 중복률 ≤ 5% |
| **검증 방법** | 규칙 기반 + LLM 자기 검증 |
| **실패 시 처리** | 자동 재시도 1회 (부족 영역 보충 생성) → 실패 시 에스컬레이션 |

**[Human Review #1]**: 생성된 질문 리스트를 사용자에게 제시. 수정/삭제/추가 가능.

---

### 2.4 Phase C: AI 테스팅 (AI Testing Agent) — 웹 자동화 중심

| 항목 | 내용 |
|------|------|
| **수행 주체** | AI Testing Agent (스크립트 중심 + LLM 조율) |
| **입력** | `question_set.json` (Human Review 반영 완료) |
| **출력** | `raw_responses/{model_name}/responses.json` + 스크린샷 |
| **핵심 도구** | Playwright (Python) |

#### 2.4.1 아키텍처 개요

```
AI Testing Agent
    │
    ├── [채널 1] ChatGPT 웹 자동화 (1순위)
    │   ├── 세션 관리 (로그인/쿠키)
    │   ├── 질문 입력 → 응답 대기 → 텍스트 추출
    │   ├── 스크린샷 캡처 (에비던스)
    │   └── 실패 시 → OpenAI API 폴백
    │
    ├── [채널 2] Google AI Overview 웹 자동화
    │   ├── 검색 쿼리 입력
    │   ├── AI Overview 스니펫 존재 여부 확인
    │   ├── 스니펫 텍스트 + 출처 URL 추출
    │   ├── 스크린샷 캡처 (에비던스)
    │   └── AI Overview 미표시 시 → 결과에 "no_ai_overview" 기록
    │
    └── [폴백] OpenAI API
        ├── ChatGPT 웹 실패 시에만 활성화
        └── api_caller.py로 처리
```

#### 2.4.2 ChatGPT 웹 자동화 상세

**실행 흐름:**

```
1. 브라우저 런치 (Playwright, headless)
2. ChatGPT 로그인 (쿠키 기반 세션 복원)
3. 세션 유효성 확인 → 실패 시 Human 에스컬레이션 ("로그인 필요")
4. 질문 루프 시작:
   a. 새 대화 시작 (매 질문마다 새 스레드 — 맥락 오염 방지)
   b. 질문 텍스트 입력 (text_conversational 필드)
   c. 응답 완료 대기 (스트리밍 종료 감지)
   d. 응답 텍스트 추출 (DOM → plaintext)
   e. 스크린샷 캡처 → /output/screenshots/chatgpt/q0001.png
   f. 결과 저장
   g. 랜덤 딜레이 (8~15초) — 봇 감지 방지
5. 실패한 질문은 별도 리스트로 수집
6. 실패 질문 → OpenAI API 폴백 실행
```

**핵심 기술 과제와 대응:**

| 과제 | 대응 전략 |
|------|----------|
| **로그인 세션 유지** | 초기 수동 로그인 → 쿠키 export → 이후 자동 복원. 세션 만료 시 Human 에스컬레이션 |
| **응답 완료 감지** | "Stop generating" 버튼 소멸 감지 + 텍스트 길이 변화 없음 (2초 간격 체크, 안정화 3회 연속) |
| **DOM 셀렉터 관리** | `references/chatgpt_selectors.json`에 셀렉터 집중 관리. 변경 시 이 파일만 업데이트 |
| **CAPTCHA/봇 감지** | 랜덤 딜레이 + 마우스 움직임 시뮬레이션. CAPTCHA 감지 시 → 일시 정지 + Human 에스컬레이션 |
| **새 대화 강제** | 매 질문마다 "New chat" 클릭으로 격리. 이전 맥락 오염 방지 |
| **모델 버전 기록** | 응답 시점의 ChatGPT 모델 표시 텍스트 캡처 (예: "ChatGPT 4o") |

**ChatGPT 셀렉터 관리 파일:**

```
references/chatgpt_selectors.json
{
  "version": "2025-03-19",
  "login": {
    "cookie_restore_url": "https://chat.openai.com",
    "session_check_selector": "[data-testid='profile-button']",
    "login_required_indicator": "button:has-text('Log in')"
  },
  "chat": {
    "new_chat_button": "nav a:first-child",
    "input_textarea": "#prompt-textarea",
    "send_button": "[data-testid='send-button']",
    "response_container": "[data-message-author-role='assistant']",
    "stop_button": "[aria-label='Stop generating']",
    "model_indicator": "[data-testid='model-selector']"
  },
  "notes": "셀렉터는 ChatGPT UI 업데이트 시 깨질 수 있음. 실패 시 이 파일을 우선 확인."
}
```

#### 2.4.3 Google AI Overview 웹 자동화 상세

**실행 흐름:**

```
1. 브라우저 런치 (Playwright, headless)
2. Google 검색 페이지 로드
3. 질문 루프 시작:
   a. 검색 쿼리 입력 (text_search 필드)
   b. 검색 결과 페이지 로드 대기
   c. AI Overview 스니펫 존재 여부 확인
      → 존재: 스니펫 텍스트 + 출처 URL 추출
      → 미존재: "no_ai_overview" 기록 (이것도 유의미한 데이터)
   d. 스크린샷 캡처 → /output/screenshots/google_aio/q0001.png
   e. 결과 저장
   f. 랜덤 딜레이 (5~10초)
4. Google 지역/언어 설정: 한국 (hl=ko, gl=kr)
```

**Google AI Overview 고유 과제:**

| 과제 | 대응 전략 |
|------|----------|
| **AI Overview 표시 불확실** | 모든 검색어에 AI Overview가 뜨지 않음. 미표시 자체가 분석 데이터 |
| **"더 보기" 펼치기** | AI Overview가 접힌 상태면 "Show more" 클릭하여 전체 텍스트 수집 |
| **출처 URL 추출** | AI Overview 하단의 출처 카드에서 URL 파싱 → Reference 필드 매핑 |
| **지역화** | URL 파라미터 (`hl=ko&gl=kr`)로 한국 검색 결과 고정 |
| **봇 감지** | User-Agent 로테이션 + 자연스러운 딜레이. reCAPTCHA 감지 시 → 일시 정지 |

**Google AI Overview 셀렉터 관리 파일:**

```
references/google_aio_selectors.json
{
  "version": "2025-03-19",
  "search": {
    "url_template": "https://www.google.com/search?q={query}&hl=ko&gl=kr",
    "search_input": "textarea[name='q']",
    "search_button": "input[name='btnK']"
  },
  "ai_overview": {
    "container": "[data-attrid='ai-overview']",
    "fallback_container": ".kp-wholepage",
    "show_more_button": "[jsname='Cpkphb']",
    "text_content": ".ai-overview-text",
    "source_cards": ".source-card a",
    "not_present_indicator": null
  },
  "notes": "Google은 DOM을 자주 변경함. 복수의 폴백 셀렉터 유지 필요."
}
```

#### 2.4.4 OpenAI API 폴백

ChatGPT 웹 자동화가 실패한 질문에 대해서만 실행된다.

| 처리 항목 | 방식 |
|-----------|------|
| API 호출 | 스크립트 (`scripts/api_caller.py`) — 결정론적 |
| Rate limiting | 스크립트 — RPM/TPM 기반 throttling |
| 재시도 (API 에러) | 스크립트 — 지수 백오프, 최대 3회 |
| 응답 파싱/저장 | 스크립트 — JSON 구조화 |

#### 2.4.5 응답 데이터 구조

```
raw_responses/chatgpt_web/responses.json
{
  "model": "ChatGPT 4o",
  "model_provider": "chatgpt_web",
  "collection_method": "web_automation",
  "queried_at": "2025-03-19T...",
  "browser_info": {"playwright_version": "1.42", "headless": true},
  "total_questions": 80,
  "successful": 76,
  "failed_to_api_fallback": 3,
  "failed_skipped": 1,
  "responses": [
    {
      "question_id": "q0001",
      "question_text": "65인치 TV 추천해줘. AI 기능이 좋은 걸로.",
      "answer_text": "65인치 TV 중 AI 기능이 뛰어난 모델은...",
      "collection_method": "web_automation",
      "response_time_ms": 8500,
      "screenshot_path": "screenshots/chatgpt/q0001.png",
      "model_version_displayed": "ChatGPT 4o",
      "references": [],
      "raw_html": "<div>...</div>"
    },
    ...
  ]
}

raw_responses/google_ai_overview/responses.json
{
  "model": "Google AI Overview",
  "model_provider": "google_ai_overview",
  "collection_method": "web_automation",
  "queried_at": "2025-03-19T...",
  "total_questions": 80,
  "ai_overview_shown": 62,
  "ai_overview_not_shown": 18,
  "responses": [
    {
      "question_id": "q0001",
      "search_query": "65인치 TV AI 기능 추천 2025",
      "ai_overview_present": true,
      "answer_text": "AI 기능이 뛰어난 65인치 TV로는...",
      "collection_method": "web_automation",
      "screenshot_path": "screenshots/google_aio/q0001.png",
      "references": [
        {"url": "https://www.samsung.com/...", "title": "삼성 Neo QLED"},
        {"url": "https://rtings.com/...", "title": "Best 65 Inch TVs"}
      ],
      "raw_html": "<div>...</div>"
    },
    {
      "question_id": "q0042",
      "search_query": "TV 블루투스 연결 방법",
      "ai_overview_present": false,
      "answer_text": null,
      "screenshot_path": "screenshots/google_aio/q0042.png",
      "references": [],
      "notes": "AI Overview 미표시 — 일반 검색 결과만 노출"
    },
    ...
  ]
}
```

#### 2.4.6 QA 스킬 검증 (응답 수집)

| 검증 항목 | 기준 | 방법 |
|-----------|------|------|
| 완료율 | 모든 질문에 대해 응답 수집 시도 완료 | 규칙 기반 (시도 수 == 질문 수) |
| 유효 응답률 | ChatGPT: ≥ 90% (폴백 포함), Google AIO: ≥ 60% (AIO 미표시 포함) | 규칙 기반 |
| 응답 비어있음 | 빈 응답 또는 에러 응답 감지 | 규칙 기반 (길이 체크 + 에러 패턴) |
| 스크린샷 존재 | 모든 시도에 대해 스크린샷 파일 존재 | 규칙 기반 (파일 존재 체크) |
| 폴백 추적 | API 폴백된 질문이 명확히 태깅되어 있는가 | 규칙 기반 (collection_method 필드) |

| 검증 | 내용 |
|------|------|
| **성공 기준** | ChatGPT 유효 응답 ≥ 90% (폴백 포함), Google AIO 시도 100% 완료 |
| **검증 방법** | 규칙 기반 |
| **실패 시 처리** | 개별 실패: 재시도 1회 → 폴백(ChatGPT만) → 스킵+로그. 전체 세션 실패: Human 에스컬레이션 |

---

### 2.5 Phase D: 데이터 구조화 + 분석 (Analysis Agent)

| 항목 | 내용 |
|------|------|
| **수행 주체** | Analysis Agent (LLM 판단 + 스크립트) |
| **입력** | `raw_responses/*/responses.json` |
| **출력** | `output/geo_analysis_{model}.csv` + `output/analysis_{model}.json` |

이 Phase는 시스템의 핵심 브릿지로, 원본 응답을 기존 `geo-report` 스킬이 소비할 수 있는 CSV 스키마로 변환한다.

**Step D-1: 응답 분석 + 구조화 (LLM 판단)**

각 AI 응답에 대해 LLM이 다음을 수행:

| 분석 항목 | 수행 주체 | 설명 |
|-----------|----------|------|
| 브랜드 멘션 추출 | LLM | 답변에서 언급된 모든 브랜드명 + 횟수 + 순서 |
| 타겟 브랜드 Position | LLM | 타겟 브랜드가 몇 번째로 언급되는지 |
| Sentiment 분류 | LLM | 타겟 브랜드에 대한 감성 + 0~1 점수 |
| Competitor 식별 | LLM | 경쟁사 브랜드 목록 추출 |
| Reference URL 추출 | 스크립트 | Google AIO: 출처 카드 파싱 / ChatGPT: 응답 내 URL 체크 |
| 태그 추출 | LLM | 답변의 핵심 키워드/태그 |

**Google AI Overview "미표시" 처리:**
- `ai_overview_present: false`인 질문 → CSV에서 `Target Brand Mentions(Count) = 0`, `Sentiment(Category) = N/A`
- 미표시 비율 자체가 중요한 분석 지표: "이 카테고리에서 Google은 AI 답변을 제공하지 않음"

**Step D-2: CSV 생성 (스크립트)**

```
필수 컬럼 매핑:
Query ID          ← question_id
Query Text        ← question_text (대화형 또는 검색형)
Answer Text       ← answer_text (null이면 "AI Overview 미표시" 기록)
Category          ← question.category
Type              ← question.type
Tags              ← LLM 추출 태그 (쉼표 구분)
Persona           ← question.persona
Target Brand Mentions(Count)    ← LLM 추출 멘션 수
Target Brand Mentions(Position) ← LLM 추출 포지션
Total Mentions(All Brands)      ← LLM 추출 전체 브랜드 멘션 수
Sentiment(Category)             ← LLM 판단 (Positive/Neutral/Negative)
Sentiment(Score)                ← LLM 판단 (0~1)
Reference                       ← Google AIO: 출처 URL / ChatGPT: 응답 내 URL
Competitor(Brand)               ← LLM 추출 경쟁사
```

**멀티모델 처리 전략:**
- 모델별 별도 CSV → 독립 분석
- 통합 CSV → `AI_Model` + `Collection_Method` 컬럼 추가
- 파일명: `geo_analysis_{model}_{brand}_{date}.csv`

**Step D-3: 정량 분석 (기존 analyze_csv.py 활용)**

```bash
python3 analyze_csv.py output/geo_analysis_chatgpt_web_Samsung_2025-03.csv \
  --brand "Samsung" --output output/analysis_chatgpt_web.json

python3 analyze_csv.py output/geo_analysis_google_aio_Samsung_2025-03.csv \
  --brand "Samsung" --output output/analysis_google_aio.json
```

**QA 스킬 검증 (데이터 무결성):**

| 검증 항목 | 기준 | 방법 |
|-----------|------|------|
| CSV 스키마 | 필수 컬럼 모두 존재, 타입 일치 | 스키마 검증 |
| 데이터 완전성 | CSV 행 수 == 유효 응답 수 | 규칙 기반 |
| Sentiment 일관성 | Score와 Category 논리적 일치 | 규칙 기반 |
| 멘션 수 정확성 | 샘플 10개에 대해 원본과 대조 | LLM 자기 검증 |
| 폴백 태깅 | API 폴백 응답이 정확히 표기되었는가 | 규칙 기반 |
| analyze_csv.py 실행 | JSON 출력 + 필수 키 존재 | 스키마 검증 |

| 검증 | 내용 |
|------|------|
| **성공 기준** | CSV 스키마 100%, 완전성 100%, 멘션 샘플 정확도 ≥ 90% |
| **검증 방법** | 스키마 + 규칙 + LLM 샘플 검증 |
| **실패 시 처리** | 스키마/완전성 → 재시도 1회. 정확도 → 전체 재분석 1회 → 에스컬레이션 |

**[Human Review #2]**: 분석 요약 + 모델 간 비교 + AI Overview 커버리지를 사용자에게 제시.

---

### 2.6 Phase E-1: 리포트 생성 (Report Agent)

| 항목 | 내용 |
|------|------|
| **수행 주체** | Report Agent → 기존 `geo-report` 스킬 호출 |
| **입력** | CSV + JSON |
| **출력** | `.docx` 리포트 |

기존 geo-report 스킬을 그대로 활용. 멀티모델 시:
- **기본**: 모델별 독립 리포트
- **추가**: 크로스모델 비교 섹션 (ChatGPT vs Google AI Overview)
- **특수**: Google AI Overview 미표시 패턴 분석

| 검증 | 내용 |
|------|------|
| **성공 기준** | .docx 생성, 페이지 ≥ 10, 필수 섹션 포함 |
| **검증 방법** | 규칙 + LLM 자기 검증 |
| **실패 시 처리** | 재시도 1회 → 에스컬레이션 |

---

### 2.7 Phase E-2: 대시보드 생성 (Dashboard Agent)

| 항목 | 내용 |
|------|------|
| **수행 주체** | Dashboard Agent (LLM 생성) |
| **입력** | JSON + CSV |
| **출력** | `output/dashboard/index.html` (단일 파일 React + Recharts) |

**대시보드 구성 요소:**

| 섹션 | 시각화 (Recharts) | 인터랙션 |
|------|-------------------|----------|
| Overview KPI | Visibility, SoV, Sentiment 카드 | 모델별 토글 (ChatGPT vs Google AIO) |
| Brand SoV | `<PieChart>` + `<BarChart>` | 카테고리 필터 |
| Category × Type | `<Treemap>` | 셀 클릭 → 질문 드릴다운 |
| Persona 분석 | `<RadarChart>` | 그룹 선택 |
| Sentiment 분포 | `<BarChart>` (스택) | 필터 |
| Reference 도메인 | `<Treemap>` | 도메인 유형별 |
| 크로스모델 비교 | `<BarChart>` (그룹) | 모델 토글 |
| AI Overview 커버리지 | `<BarChart>` | 카테고리별 표시/미표시 |
| 질문별 상세 | 데이터 테이블 | 검색, 정렬, 스크린샷 링크 |

**기술 스택:** React + Recharts + Tailwind CSS (CDN, 단일 HTML)

| 검증 | 내용 |
|------|------|
| **성공 기준** | 에러 없이 렌더링, 차트 데이터 표시, 필터 작동 |
| **검증 방법** | 규칙 + LLM 코드 리뷰 |
| **실패 시 처리** | 재시도 1회 → 에스컬레이션 |

**[Human Review #3]**: 리포트 + 대시보드 최종 확인.

---

### 2.8 QA 스킬 상세

공유 스킬로 설계 (독립 에이전트 아님).

| Phase | 검증 대상 | QA 유형 | 실패 시 |
|-------|----------|---------|---------|
| B | question_set.json | 규칙 + LLM | 재생성 → Human |
| C | raw_responses/*.json | 규칙 | 재시도/폴백 → 스킵 |
| D | CSV + JSON | 스키마 + 규칙 + LLM | 재분석 → Human |
| E-1 | .docx | 규칙 + LLM | 재생성 → Human |
| E-2 | .html | 규칙 + LLM | 재생성 → Human |

---

### 2.9 Human-in-the-Loop 상세

| 시점 | 제시 내용 | 사용자 선택지 | 기본값 |
|------|----------|-------------|--------|
| **HR#1** | 질문 목록 + 분포 + 검색형 미리보기 | 승인 / 수정 / 재생성 | 승인 |
| **HR#2** | KPI 요약 + 모델 비교 + AIO 커버리지 | 승인 / 추가 분석 / 중단 | 승인 |
| **HR#3** | 리포트 + 대시보드 | 승인 / 수정 지시 | 반드시 확인 |
| **HR#긴급** | "ChatGPT 세션 만료" | 쿠키 재제공 / API 전환 / 중단 | 반드시 확인 |

---

## 3. 구현 스펙

### 3.1 폴더 구조

```
/geo-cli/
├── CLAUDE.md                           # Orchestrator 지침
├── /.claude/
│   ├── /skills/
│   │   ├── /question-generator/
│   │   │   ├── SKILL.md
│   │   │   └── /references/
│   │   │       └── question_types.md
│   │   │
│   │   ├── /ai-tester/
│   │   │   ├── SKILL.md                # 웹 자동화 + API 폴백 가이드
│   │   │   ├── /scripts/
│   │   │   │   ├── chatgpt_automator.py    # ChatGPT 웹 (Playwright)
│   │   │   │   ├── google_aio_automator.py # Google AI Overview (Playwright)
│   │   │   │   ├── api_caller.py           # OpenAI API 폴백
│   │   │   │   ├── session_manager.py      # 쿠키/세션 관리
│   │   │   │   └── response_parser.py      # 웹/API 응답 정규화
│   │   │   └── /references/
│   │   │       ├── chatgpt_selectors.json
│   │   │       ├── google_aio_selectors.json
│   │   │       └── model_configs.json
│   │   │
│   │   ├── /response-analyzer/
│   │   │   ├── SKILL.md
│   │   │   ├── /scripts/
│   │   │   │   ├── csv_builder.py
│   │   │   │   └── analyze_csv.py      # geo-report에서 가져옴
│   │   │   └── /references/
│   │   │       └── csv_schema.md
│   │   │
│   │   ├── /qa-checker/
│   │   │   ├── SKILL.md
│   │   │   └── /scripts/
│   │   │       └── validators.py
│   │   │
│   │   ├── /dashboard-builder/
│   │   │   ├── SKILL.md
│   │   │   └── /references/
│   │   │       └── dashboard_template.html
│   │   │
│   │   └── /geo-report/                # 기존 스킬 연동
│   │       ├── SKILL.md
│   │       ├── /scripts/
│   │       │   └── analyze_csv.py
│   │       └── /references/
│   │           ├── report_structure.md
│   │           └── docx_style_guide.md
│   │
│   └── /agents/
│       ├── /question-agent/
│       │   └── AGENT.md
│       ├── /testing-agent/
│       │   └── AGENT.md
│       ├── /analysis-agent/
│       │   └── AGENT.md
│       ├── /report-agent/
│       │   └── AGENT.md
│       └── /dashboard-agent/
│           └── AGENT.md
│
├── /output/
│   ├── analysis_brief.json
│   ├── question_set.json
│   ├── /raw_responses/
│   │   ├── /chatgpt_web/
│   │   ├── /google_ai_overview/
│   │   └── /openai_api_fallback/
│   ├── /screenshots/
│   │   ├── /chatgpt/
│   │   └── /google_aio/
│   ├── geo_analysis_chatgpt_web_Samsung_2025-03.csv
│   ├── geo_analysis_google_aio_Samsung_2025-03.csv
│   ├── geo_analysis_combined_Samsung_2025-03.csv
│   ├── analysis_chatgpt_web.json
│   ├── analysis_google_aio.json
│   ├── GEO_분석_리포트_Samsung_chatgpt_web_2025-03.docx
│   ├── /dashboard/
│   │   └── index.html
│   └── /logs/
│       └── execution_log.json
│
├── /config/
│   ├── api_keys.env                    # gitignore
│   └── chatgpt_cookies.json            # gitignore
│
└── /docs/
    └── csv_schema_reference.md
```

### 3.2 CLAUDE.md 핵심 섹션 목록

| 섹션 | 역할 |
|------|------|
| 프로젝트 개요 | 목적과 범위 |
| 워크플로우 총괄 | Phase A~E + Human Review |
| 웹 자동화 전략 | 웹 우선 / API 폴백 / 세션 관리 |
| 서브에이전트 매핑 | 이름 → 경로 → 트리거 |
| 스킬 매핑 | 이름 → 경로 → 사용 에이전트 |
| 데이터 플로우 | Phase 간 파일 경로 규칙 |
| Human Review 프로토콜 | HR#1~3 + HR#긴급 |
| 실패 처리 총괄 | 재시도/폴백/에스컬레이션 |
| 셀렉터 유지보수 | DOM 변경 대응 절차 |
| 실행 로그 규칙 | 포맷 + 기록 시점 |

### 3.3 에이전트 구조

```
Orchestrator (CLAUDE.md)
    │
    ├── Question Agent
    │   └── 스킬: question-generator, qa-checker
    │
    ├── AI Testing Agent  ← 가장 복잡 (웹 자동화 + API 폴백 + 세션)
    │   └── 스킬: ai-tester, qa-checker
    │
    ├── Analysis Agent
    │   └── 스킬: response-analyzer, qa-checker
    │
    ├── Report Agent
    │   └── 스킬: geo-report, qa-checker
    │
    └── Dashboard Agent
        └── 스킬: dashboard-builder, qa-checker
```

### 3.4 서브에이전트 상세

| 에이전트 | 역할 | 입력 | 출력 | 트리거 |
|----------|------|------|------|--------|
| Question Agent | 질문 세트 생성 (대화형+검색형) | analysis_brief.json | question_set.json | Phase A 완료 |
| AI Testing Agent | 웹 자동화 질의 + 스크린샷 수집 | question_set.json | raw_responses/* + screenshots/* | HR#1 승인 |
| Analysis Agent | 응답 분석 → CSV/JSON | raw_responses/* | CSV + JSON | Phase C 완료 |
| Report Agent | Word 리포트 (기존 스킬) | CSV + JSON | .docx | HR#2 승인 |
| Dashboard Agent | React + Recharts 대시보드 | JSON + CSV | .html | HR#2 승인 (병렬) |

### 3.5 스킬 목록

| 스킬 | 역할 | 사용 에이전트 |
|------|------|-------------|
| `question-generator` | 질문 생성, 타입 분류, 검색형 변환 | Question Agent |
| `ai-tester` | 웹 자동화, API 폴백, 세션/셀렉터 관리 | AI Testing Agent |
| `response-analyzer` | 응답 분석(LLM), CSV 변환, 정량 분석 | Analysis Agent |
| `qa-checker` | 검증 함수 모음 | 전체 공유 |
| `dashboard-builder` | React+Recharts 대시보드 가이드 | Dashboard Agent |
| `geo-report` | Word 리포트 (기존) | Report Agent |

### 3.6 스크립트 목록

| 스크립트 | 위치 | 역할 |
|----------|------|------|
| `chatgpt_automator.py` | ai-tester/scripts/ | ChatGPT 웹 자동화 (Playwright) |
| `google_aio_automator.py` | ai-tester/scripts/ | Google AI Overview 자동화 |
| `api_caller.py` | ai-tester/scripts/ | OpenAI API 폴백 |
| `session_manager.py` | ai-tester/scripts/ | 쿠키/세션 관리 |
| `response_parser.py` | ai-tester/scripts/ | 웹/API 응답 정규화 |
| `csv_builder.py` | response-analyzer/scripts/ | 분석 결과 → CSV 변환 |
| `analyze_csv.py` | response-analyzer/scripts/ | 기존 정량 분석 |
| `validators.py` | qa-checker/scripts/ | 검증 함수 모음 |

### 3.7 데이터 전달 패턴

```
Phase A → B:  /output/analysis_brief.json
Phase B → C:  /output/question_set.json
Phase C → D:  /output/raw_responses/{model}/responses.json
              /output/screenshots/{model}/q*.png
Phase D → E:  /output/geo_analysis_{model}_{brand}_{date}.csv
              /output/analysis_{model}.json
```

### 3.8 주요 산출물 파일 형식

| 파일 | 형식 | 크기 예상 |
|------|------|----------|
| analysis_brief.json | JSON | ~2KB |
| question_set.json | JSON | ~80KB |
| raw_responses/{model}/ | JSON | ~500KB~1MB/모델 |
| screenshots/{model}/ | PNG × 80장 | ~20MB/모델 |
| geo_analysis_{model}.csv | CSV | ~200KB |
| analysis_{model}.json | JSON | ~100KB |
| 리포트 .docx | Word | ~2MB |
| dashboard/index.html | HTML | ~500KB |
| execution_log.json | JSON | ~20KB |

---

## 4. 구현 전 체크리스트

### Phase 1 (MVP)
- [ ] **Playwright 환경 구성**: `pip install playwright && playwright install chromium`
- [ ] **ChatGPT 세션 확보**: 수동 로그인 → 쿠키 export → `chatgpt_cookies.json`
- [ ] **ChatGPT 셀렉터 조사**: input/output/new-chat 셀렉터 → `chatgpt_selectors.json`
- [ ] **Google AI Overview 셀렉터 조사**: AIO 컨테이너, 출처 카드 → `google_aio_selectors.json`
- [ ] **OpenAI API 키 확보** (폴백용)
- [ ] `analyze_csv.py` 프로젝트 연동 + CSV 스키마 호환 테스트
- [ ] **봇 감지 방지 테스트**: 딜레이, User-Agent, 마우스 시뮬레이션
- [ ] **Playwright stealth 검토**: `playwright-extra` 또는 동등 라이브러리

### Phase 2 (확장)
- [ ] Perplexity 웹 자동화 (출처 URL 수집)
- [ ] Gemini 웹/API
- [ ] 월별 Baseline 자동 비교
- [ ] 멀티 브랜드 동시 분석
- [ ] 셀렉터 자동 복구 메커니즘

---

## 5. 리스크 및 고려사항

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| ChatGPT DOM 변경 | 높음 | Phase C 중단 | 셀렉터 JSON 분리 관리. LLM 자동 재조사 → Human |
| ChatGPT 세션 만료 | 높음 | Phase C 중단 | 매 실행 전 체크. HR#긴급 발동 |
| ChatGPT 봇 감지 | 중간 | 일부 실패 | 랜덤 딜레이 + stealth. 차단 시 전체 API 폴백 |
| Google AIO 미표시 | 높음 | 데이터 불완전 | 미표시 자체를 분석 데이터로 활용 |
| Google DOM 변경 | 높음 | AIO 추출 실패 | 복수 폴백 셀렉터 |
| LLM 분석 일관성 | 중간 | CSV 품질 저하 | temperature 0 + QA 샘플 검증 |
| Playwright headless 감지 | 중간 | 봇 차단 | stealth 플러그인 |
| 스크린샷 용량 | 낮음 | 디스크 | 압축/리사이즈 |

---

## 6. 설계 결정 근거 요약

| 결정 | 선택 | 근거 |
|------|------|------|
| 웹 vs API | 웹 우선, API 폴백 | 실제 소비자 경험 + 비용 절감 + Google AIO API 없음 |
| Phase 1 타겟 | ChatGPT 웹 + Google AIO | 가장 보편적 생성AI + 검색 맥락 AI 노출 |
| QA 구조 | 공유 스킬 | Phase별 검증 로직 상이, 독자 도메인 불필요 |
| 대시보드 | React + Recharts (단일 HTML) | Claude Code 직접 생성, CDN, 인터랙티브 |
| 질문 이중 생성 | 대화형 + 검색형 | ChatGPT=대화, Google AIO=검색 |
| 셀렉터 관리 | JSON 파일 분리 | DOM 변경 시 스크립트 수정 없이 JSON만 업데이트 |
| 세션 관리 | 쿠키 기반 + 수동 초기화 | 자동 로그인은 보안 리스크 |
| 스크린샷 | 전 질문 캡처 | 웹 자동화 신뢰성 검증 + 리포트 첨부 |