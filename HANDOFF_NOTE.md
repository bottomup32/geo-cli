# GEO CLI — 인수인계 노트

**작성일:** 2026-03-20
**상태:** MVP Phase 1 파이프라인 전체 구현 완료

---

## 현재 구현 상태

```
GEO CLI/
├── geo_cli/
│   ├── main.py                    ✅ 전체 파이프라인 연결
│   ├── orchestrator/
│   │   ├── schema.py              ✅ AnalysisBrief 데이터 모델
│   │   ├── prompts.py             ✅ Claude 시스템 프롬프트
│   │   └── agent.py               ✅ 인터뷰 상태 머신
│   ├── agents/
│   │   ├── query_agent.py         ✅ 쿼리 생성 (Claude API)
│   │   ├── testing_agent.py       ✅ ChatGPT.com 스크래핑 (Playwright)
│   │   ├── analysis_agent.py      ✅ GEO 지표 계산 (Claude API)
│   │   └── report_agent.py        ✅ 컨설팅 보고서 생성 (Claude API 스트리밍)
│   ├── ui/
│   │   └── console.py             ✅ Rich 터미널 UI
│   └── utils/
│       └── file_io.py             ✅ JSON 저장/로드
├── data/                          (실행 시 자동 생성)
│   ├── brief_{id}.json            ← Orchestrator 출력
│   ├── queries_{id}.json/.csv     ← Query Agent 출력
│   ├── raw_chatgpt_{id}.json/.csv ← Testing Agent 출력
│   ├── raw_chatgpt_{id}.partial.json  ← 중간 저장 (크래시 대비)
│   ├── analysis_{id}.json/.csv    ← Analysis Agent 출력
│   └── report_{id}.md             ← Report Agent 출력
├── requirements.txt               ✅ (anthropic, rich, python-dotenv, playwright)
├── pyproject.toml                 ✅ (build-backend 수정됨)
└── .env                           ← 직접 생성 필요 (.env.example 참고)
```

---

## 실행 방법

```bash
# 1. .env 파일 생성 (.env.example 복사 후 API 키 입력)
# ANTHROPIC_API_KEY=실제키
# GEO_MODEL=claude-sonnet-4-6
# GEO_DATA_DIR=./data

# 2. 패키지 설치
pip install -e .
playwright install chromium  # 아직 안 했다면

# 3. 실행
python -m geo_cli
# 또는
geo
```

---

## 파이프라인 흐름

```
1. Orchestrator   → 대화형 인터뷰 → AnalysisBrief (승인 후 저장)
2. Query Agent    → Claude로 50~100개 쿼리 생성 → 사용자 검토/승인
3. Testing Agent  → Playwright로 ChatGPT.com 쿼리 실행 → 응답 저장
4. Analysis Agent → Claude 배치 분석 → GEO 지표 계산 → CSV/JSON 저장
5. Report Agent   → Claude 스트리밍 → 컨설팅 보고서 (.md) 저장
```

---

## 다음 작업 (우선순위)

| 순서 | 작업 | 설명 |
|------|------|------|
| 1 | **실제 실행 테스트** | .env 설정 후 end-to-end 테스트, ChatGPT 셀렉터 검증 |
| 2 | **ChatGPT 셀렉터 안정화** | `testing_agent.py` 상단 `_SEL_*` 상수를 실제 UI에 맞게 조정 |
| 3 | **Google AI Mode** | `testing_agent.py`에 두 번째 플랫폼 추가 |
| 4 | **보고서 포맷 개선** | `.md` → PDF 변환 옵션, 로고/스타일 추가 |
| 5 | **Dashboard Agent** | Phase 2: 시계열 추적 웹 앱 |

---

## ChatGPT 셀렉터 (UI 변경 시 여기만 수정)

`geo_cli/agents/testing_agent.py` 상단:

```python
_SEL_INPUT    = "#prompt-textarea"
_SEL_SEND     = "[data-testid='send-button']"
_SEL_STOP     = "[data-testid='stop-button']"
_SEL_RESPONSE = "[data-message-author-role='assistant']"
_SEL_CITATION = "[data-message-author-role='assistant'] a[href]"
```

---

## 수정된 버그 (이전 세션 대비)

- `pyproject.toml` build-backend: `setuptools.backends.legacy:build` → `setuptools.build_meta`
- `schema.py` Subject, Persona, TargetPlatform 필수 필드에 기본값 추가 (default_factory 호환)
