"""GEO CLI — Streamlit 웹 UI"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv, set_key

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

st.set_page_config(
    page_title="GEO CLI — TecAce",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

SENTINEL = "<INTERVIEW_COMPLETE>"
DATA_DIR = Path(os.getenv("GEO_DATA_DIR", str(ROOT / "data")))
PROMPTS_DIR = ROOT / "prompts"
ENV_FILE = ROOT / ".env"
DATA_DIR.mkdir(exist_ok=True)

# ── 프롬프트 파일 관리 ─────────────────────────────────────────────────────────
def _load_default_prompts() -> dict[str, str]:
    from geo_cli.orchestrator.prompts import SYSTEM_PROMPT as orch
    from geo_cli.agents.query_agent import _SYSTEM_PROMPT as query
    from geo_cli.agents.analysis_agent import _ANALYSIS_SYSTEM as analysis
    from geo_cli.agents.report_agent import _REPORT_SYSTEM as report
    return {"orchestrator": orch, "query_agent": query, "analysis": analysis, "report": report}

def _ensure_prompt_files() -> None:
    PROMPTS_DIR.mkdir(exist_ok=True)
    if not any(PROMPTS_DIR.glob("*.txt")):
        for name, content in _load_default_prompts().items():
            (PROMPTS_DIR / f"{name}.txt").write_text(content, encoding="utf-8")

def get_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else _load_default_prompts().get(name, "")

def save_prompt(name: str, content: str) -> None:
    PROMPTS_DIR.mkdir(exist_ok=True)
    (PROMPTS_DIR / f"{name}.txt").write_text(content, encoding="utf-8")

_ensure_prompt_files()

# ── Session state 초기화 ──────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "page": "💬 인터뷰",
    "chat": [],
    "brief_dict": None,
    "brief": None,
    "query_result": None,
    "testing_result": None,
    "analysis_result": None,
    "report_path": None,
    "interview_done": False,
}
for _k, _v in _DEFAULTS.items():
    st.session_state.setdefault(_k, _v)

_api_key = os.getenv("ANTHROPIC_API_KEY", "")
_model   = os.getenv("GEO_MODEL", "claude-sonnet-4-6")

# ── 사이드바 네비게이션 ───────────────────────────────────────────────────────
PAGES = ["💬 인터뷰", "▶ 파이프라인", "📂 데이터", "🔧 프롬프트 편집", "⚙️ 설정"]

with st.sidebar:
    st.markdown("## 🎯 GEO CLI")
    st.caption("TecAce Software — v0.1")
    st.divider()

    # 메뉴 버튼
    for page in PAGES:
        is_current = st.session_state.page == page
        if st.button(
            page,
            key=f"nav_{page}",
            use_container_width=True,
            type="primary" if is_current else "secondary",
        ):
            st.session_state.page = page
            st.rerun()

    st.divider()

    # 파이프라인 상태
    st.markdown("**파이프라인 상태**")
    steps = [
        ("📋 브리프",  st.session_state.brief),
        ("📝 쿼리",    st.session_state.query_result),
        ("🤖 테스트",  st.session_state.testing_result),
        ("📊 분석",    st.session_state.analysis_result),
        ("📄 보고서",  st.session_state.report_path),
    ]
    for label, val in steps:
        st.write(f"{'✅' if val else '⬜'} {label}")

    if st.session_state.brief:
        b = st.session_state.brief
        st.caption(f"📌 {b.subject.name}")
        st.caption(f"🆔 `{b.brief_id}`")

    st.divider()
    if st.button("🔄 새 분석 시작", use_container_width=True):
        for k, v in _DEFAULTS.items():
            st.session_state[k] = v
        st.rerun()

# ── 현재 페이지 렌더링 ────────────────────────────────────────────────────────
current_page = st.session_state.page


# ══════════════════════════════════════════════════════════════════════════════
# 페이지 1 — 인터뷰
# ══════════════════════════════════════════════════════════════════════════════
if current_page == "💬 인터뷰":
    st.title("💬 GEO 인터뷰")

    if st.session_state.brief:
        # 이미 완료
        b = st.session_state.brief
        st.success(f"✅ 브리프 완성: **{b.subject.name}** (`{b.brief_id}`)")
        if st.button("▶ 파이프라인으로 이동", type="primary"):
            st.session_state.page = "▶ 파이프라인"
            st.rerun()
        st.stop()

    # 채팅 기록 표시
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat:
            st.info("아래에 메시지를 입력해서 인터뷰를 시작하세요.\n\n예: *'삼성전자 갤럭시 브랜드를 분석하고 싶어요.'*")

        for msg in st.session_state.chat:
            avatar = "🎯" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    # 확인 폼 (인터뷰 완료 후)
    if st.session_state.interview_done and st.session_state.brief_dict:
        st.divider()
        st.subheader("📋 수집된 정보 확인")

        bd = st.session_state.brief_dict
        s  = bd.get("subject", {})
        p  = bd.get("analysis_purpose", {})
        qs = bd.get("query_settings", {})
        rs = bd.get("report_settings", {})

        col1, col2 = st.columns(2)
        purpose_map = {"brand_awareness":"브랜드 인지도","competitive_analysis":"경쟁사 비교","content_strategy":"콘텐츠 전략","crisis_monitoring":"위기 모니터링"}
        lang_map    = {"ko":"한국어","en":"영어","ja":"일본어","zh":"중국어"}
        aud_map     = {"executive":"임원용","technical":"기술용","marketing":"마케팅용"}

        with col1:
            st.write(f"**분석 대상:** {s.get('name','—')} ({s.get('type','—')})")
            st.write(f"**산업:** {s.get('industry','—')} | **시장:** {s.get('primary_market','—')}")
            if s.get("website"): st.write(f"**웹사이트:** {s.get('website')}")
            st.write(f"**분석 목적:** {purpose_map.get(p.get('type',''), p.get('type','—'))}")

        with col2:
            comps = bd.get("competitors", [])
            if comps: st.write(f"**경쟁사:** {', '.join(c.get('name','') for c in comps)}")
            plats = [pl for pl in bd.get("target_platforms",[]) if pl.get("enabled")]
            if plats: st.write(f"**플랫폼:** {', '.join(pl.get('name','') for pl in plats)}")
            _query_count = st.number_input(
                "생성할 쿼리 수",
                min_value=5, max_value=500, step=5,
                value=qs.get("target_count", 75),
                key="confirm_query_count",
            )
            st.caption(f"언어: {', '.join(lang_map.get(l,l) for l in qs.get('query_languages',[]))}")
            if qs.get('products'): st.write(f"**제품:** {', '.join(qs.get('products', []))}")
            if qs.get('keywords'): st.write(f"**키워드:** {', '.join(qs.get('keywords', []))}")
            st.write(f"**보고서:** {aud_map.get(rs.get('audience_level',''),'—')} / {lang_map.get(rs.get('language','ko'),'—')}")

        personas = bd.get("personas", [])
        if personas:
            st.write(f"**페르소나 ({len(personas)}개):**")
            for pp in personas:
                src = "사용자 정의" if pp.get("source") == "user_defined" else "AI 추론"
                st.write(f"  • **{pp.get('name','')}** [{src}]: {pp.get('description','')}")

        st.divider()
        col_ok, col_restart = st.columns([1, 1])
        with col_ok:
            if st.button("✅ 승인 — 파이프라인 시작", type="primary", use_container_width=True):
                from geo_cli.orchestrator.schema import AnalysisBrief, _generate_brief_id
                from datetime import datetime, timezone
                from geo_cli.utils.file_io import save_brief

                # 사용자가 수정한 쿼리 수 반영
                st.session_state.brief_dict.setdefault("query_settings", {})["target_count"] = st.session_state.get("confirm_query_count", 75)

                brief = AnalysisBrief.from_dict(st.session_state.brief_dict)
                if not brief.brief_id:
                    brief.brief_id = _generate_brief_id()
                brief.created_at = datetime.now(timezone.utc).isoformat()
                brief.status = "approved"
                brief.metadata.model_used = _model
                save_brief(brief)

                st.session_state.brief = brief
                st.session_state.interview_done = False
                st.session_state.page = "▶ 파이프라인"   # 자동 이동
                st.rerun()

        with col_restart:
            if st.button("🔄 재시작", use_container_width=True):
                st.session_state.chat = []
                st.session_state.brief_dict = None
                st.session_state.interview_done = False
                st.rerun()

    else:
        # 채팅 입력
        if user_input := st.chat_input("메시지를 입력하세요…"):
            if not _api_key:
                st.error("⚠️ API 키가 없습니다. [⚙️ 설정] 메뉴에서 입력하세요.")
                st.stop()

            if not st.session_state.chat:
                from geo_cli.orchestrator.prompts import OPENING_MESSAGE
                st.session_state.chat.append({"role": "assistant", "content": OPENING_MESSAGE})

            st.session_state.chat.append({"role": "user", "content": user_input})

            import anthropic
            client = anthropic.Anthropic(api_key=_api_key)
            messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat]

            with st.chat_message("assistant", avatar="🎯"):
                placeholder = st.empty()
                full_response = ""
                visible_text  = ""
                sentinel_hit  = False

                try:
                    with client.messages.stream(
                        model=_model, max_tokens=4096,
                        system=get_prompt("orchestrator"),
                        messages=messages,
                    ) as stream:
                        for chunk in stream.text_stream:
                            full_response += chunk
                            if not sentinel_hit:
                                if SENTINEL in full_response:
                                    sentinel_hit = True
                                    visible_text = full_response.split(SENTINEL)[0]
                                else:
                                    visible_text = full_response
                                placeholder.markdown(visible_text + "▌")
                    placeholder.markdown(visible_text)
                except anthropic.APIStatusError as e:
                    st.error(f"API 오류: {e}")
                    st.stop()

            st.session_state.chat.append({"role": "assistant", "content": visible_text})

            if sentinel_hit:
                _, json_part = full_response.split(SENTINEL, 1)
                json_str = json_part.strip()
                if json_str.startswith("```"):
                    lines = json_str.splitlines()
                    json_str = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()
                try:
                    start = json_str.find("{")
                    obj, _ = json.JSONDecoder().raw_decode(json_str, start)
                    st.session_state.brief_dict  = obj
                    st.session_state.interview_done = True
                except (ValueError, json.JSONDecodeError) as e:
                    st.warning(f"JSON 파싱 오류: {e}. 계속 대화하세요.")

            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# 페이지 2 — 파이프라인
# ══════════════════════════════════════════════════════════════════════════════
elif current_page == "▶ 파이프라인":
    import threading, time
    from geo_cli.utils.stream_log import geo_log

    st.title("▶ 파이프라인")

    brief = st.session_state.brief
    if not brief:
        st.warning("먼저 **💬 인터뷰** 메뉴에서 브리프를 완성하거나, **📂 데이터** 메뉴에서 기존 브리프를 불러오세요.")
        if st.button("💬 인터뷰 시작하기", type="primary"):
            st.session_state.page = "💬 인터뷰"
            st.rerun()
        st.stop()

    st.info(f"📋 **{brief.subject.name}** — `{brief.brief_id}`")

    # ── 2열 레이아웃: 왼쪽=단계, 오른쪽=실시간 로그 ──────────────────────────
    col_steps, col_log = st.columns([3, 2])

    # ── 로그 패널 (항상 오른쪽에 표시) ────────────────────────────────────────
    with col_log:
        st.markdown("### 📋 실시간 로그")
        log_placeholder = st.empty()

        def _render_log():
            lines = geo_log.get_recent(60)
            if lines:
                log_placeholder.code("\n".join(lines), language=None)
            else:
                log_placeholder.caption("아직 로그가 없습니다. 에이전트를 실행하면 여기에 표시됩니다.")

        _render_log()

        if st.button("🗑️ 로그 지우기", key="clear_log"):
            geo_log.clear()
            st.rerun()

    # ── 헬퍼: 백그라운드 스레드로 실행하며 로그 실시간 업데이트 ──────────────
    def _run_with_live_log(fn, *args, **kwargs):
        """fn을 백그라운드 스레드로 실행, 완료까지 로그를 0.5초마다 갱신."""
        holder = {"result": None, "error": None, "done": False}

        def _worker():
            try:
                holder["result"] = fn(*args, **kwargs)
            except Exception as e:
                holder["error"] = e
            finally:
                holder["done"] = True

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        while not holder["done"]:
            _render_log()
            time.sleep(0.5)
        _render_log()  # 최종 로그

        if holder["error"]:
            raise holder["error"]
        return holder["result"]

    # ── 단계들 (왼쪽 컬럼) ────────────────────────────────────────────────────
    with col_steps:

        # ── Step 2: Query Agent ───────────────────────────────────────────────
        st.subheader("📝 Step 2 — Query Agent")
        if st.session_state.query_result:
            qr = st.session_state.query_result
            st.success(f"✅ {qr.total}개 쿼리 생성 완료")
            with st.expander("쿼리 목록 보기"):
                st.dataframe(
                    [{"ID": q.id, "언어": q.language, "유형": q.type,
                      "카테고리": q.category, "페르소나": q.persona_id, "쿼리": q.text}
                     for q in qr.queries],
                    use_container_width=True, height=300,
                )
            if st.button("🔄 쿼리 재생성", key="regen_query"):
                st.session_state.query_result = None
                geo_log.clear()
                st.rerun()
        else:
            st.write(f"목표: **{brief.query_settings.target_count}개** | 언어: **{', '.join(brief.query_settings.query_languages)}**")
            if st.button("▶ 쿼리 생성 실행", type="primary", key="run_query"):
                from geo_cli.agents.query_agent import QueryAgent
                geo_log.clear()
                try:
                    result = _run_with_live_log(
                        QueryAgent(api_key=_api_key, model=_model).run,
                        brief, False,   # interactive=False (터미널 입력 생략)
                    )
                    st.session_state.query_result = result
                    st.rerun()
                except Exception as e:
                    import traceback
                    st.error(f"오류: {e}")
                    st.code(traceback.format_exc(), language="python")

        st.divider()

        # ── Step 3: Testing Agent ─────────────────────────────────────────────
        st.subheader("🤖 Step 3 — Testing Agent (ChatGPT)")
        if st.session_state.testing_result:
            tr = st.session_state.testing_result
            c1, c2, c3 = st.columns(3)
            c1.metric("전체", tr.total)
            c2.metric("성공", tr.success)
            c3.metric("실패", tr.error)
            with st.expander("응답 목록 보기"):
                st.dataframe(
                    [{"쿼리 ID": r.query_id, "상태": r.status,
                      "응답 길이": len(r.response_text), "URL 수": len(r.response_urls)}
                     for r in tr.responses],
                    use_container_width=True,
                )
            if st.button("🔄 테스트 재실행", key="regen_test"):
                st.session_state.testing_result = None
                geo_log.clear()
                st.rerun()
        else:
            if not st.session_state.query_result:
                st.warning("먼저 쿼리를 생성하세요.")
            else:
                # Playwright 사용 가능 여부 확인
                _playwright_ok = True
                try:
                    import playwright  # noqa: F401
                except ImportError:
                    _playwright_ok = False

                if _playwright_ok:
                    st.info("⚠️ 브라우저 창이 열립니다. ChatGPT 로그인 후 자동으로 쿼리가 실행됩니다.")
                    if st.button("▶ ChatGPT 테스트 실행", type="primary", key="run_test"):
                        from geo_cli.agents.testing_agent import TestingAgent
                        geo_log.clear()
                        try:
                            result = _run_with_live_log(
                                TestingAgent().run, brief, st.session_state.query_result
                            )
                            st.session_state.testing_result = result
                            st.rerun()
                        except Exception as e:
                            import traceback
                            st.error(f"오류: {e}")
                            st.code(traceback.format_exc(), language="python")

                # ── 파일 업로드 (서버 배포 또는 로컬 실행 결과 가져오기)
                st.divider()
                st.markdown("**📤 로컬 테스트 결과 업로드**")
                if not _playwright_ok:
                    st.caption("이 서버에서는 브라우저 테스트를 실행할 수 없습니다. "
                               "로컬에서 `python -m geo_cli`로 실행한 결과 JSON 파일을 업로드하세요.")
                else:
                    st.caption("로컬에서 별도로 실행한 결과가 있으면 여기에 업로드할 수 있습니다.")

                uploaded = st.file_uploader(
                    "테스트 결과 JSON 파일 (raw_chatgpt_*.json)",
                    type=["json"], key="upload_testing",
                )
                if uploaded is not None:
                    try:
                        from geo_cli.agents.testing_agent import (
                            TestingResult, RawResponse,
                        )
                        data = json.loads(uploaded.read().decode("utf-8"))
                        responses = [
                            RawResponse(
                                query_id=r["query_id"],
                                query_text=r["query_text"],
                                platform=r.get("platform", "chatgpt"),
                                response_text=r["response_text"],
                                response_urls=r.get("response_urls", []),
                                timestamp=r.get("timestamp", ""),
                                status=r.get("status", "success"),
                                error_message=r.get("error_message", ""),
                            )
                            for r in data.get("responses", [])
                        ]
                        result = TestingResult(
                            brief_id=data.get("brief_id", brief.brief_id),
                            platform=data.get("platform", "chatgpt"),
                            responses=responses,
                            total=data.get("total", len(responses)),
                            success=data.get("success", sum(1 for r in responses if r.status == "success")),
                            error=data.get("error", sum(1 for r in responses if r.status == "error")),
                        )
                        # 결과 저장
                        from geo_cli.utils.file_io import _DEFAULT_DATA_DIR, atomic_write
                        save_path = _DEFAULT_DATA_DIR / f"raw_chatgpt_{brief.brief_id}.json"
                        atomic_write(save_path, json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
                        st.session_state.testing_result = result
                        st.success(f"✅ 업로드 완료 — {result.success}/{result.total}건 성공")
                        st.rerun()
                    except Exception as e:
                        st.error(f"JSON 파싱 오류: {e}")

        st.divider()

        # ── Step 4: Analysis Agent ────────────────────────────────────────────
        st.subheader("📊 Step 4 — Analysis Agent")
        if st.session_state.analysis_result:
            ar = st.session_state.analysis_result
            m  = ar.metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Visibility",     f"{m.visibility*100:.1f}%", f"{m.mentioned_count}/{m.total_queries}건")
            c2.metric("Share of Voice", f"{m.sov*100:.1f}%")
            c3.metric("Avg. Rank",      f"{m.avg_rank:.1f}" if m.avg_rank else "N/A")
            c4.metric("Rank 1 횟수",    f"{m.rank_1_count}회")

            cs, cc = st.columns(2)
            with cs:
                total_s = m.sentiment_positive + m.sentiment_negative + m.sentiment_neutral
                if total_s:
                    import pandas as pd
                    st.markdown("**감성 분포**")
                    st.bar_chart(pd.DataFrame(
                        {"수": [m.sentiment_positive, m.sentiment_negative, m.sentiment_neutral]},
                        index=["긍정", "부정", "중립"],
                    ))
            with cc:
                if m.competitor_metrics:
                    st.markdown("**경쟁사 언급**")
                    st.dataframe(
                        [{"경쟁사": c.name, "언급": c.mention_count, "SoV": f"{c.sov*100:.1f}%"}
                         for c in m.competitor_metrics],
                        use_container_width=True,
                    )
            if m.persona_metrics:
                import pandas as pd
                st.markdown("**페르소나별 Visibility**")
                st.bar_chart(pd.DataFrame(
                    {"Visibility (%)": [round(p.visibility*100,1) for p in m.persona_metrics]},
                    index=[p.persona_name for p in m.persona_metrics],
                ))
            if st.button("🔄 분석 재실행", key="regen_analysis"):
                st.session_state.analysis_result = None
                geo_log.clear()
                st.rerun()
        else:
            if not st.session_state.testing_result:
                st.warning("먼저 Testing Agent를 실행하세요.")
            else:
                if st.button("▶ 분석 실행", type="primary", key="run_analysis"):
                    from geo_cli.agents.analysis_agent import AnalysisAgent
                    geo_log.clear()
                    try:
                        result = _run_with_live_log(
                            AnalysisAgent(api_key=_api_key, model=_model).run,
                            brief,
                            st.session_state.testing_result,
                            st.session_state.query_result,
                        )
                        st.session_state.analysis_result = result
                        st.rerun()
                    except Exception as e:
                        import traceback
                        st.error(f"오류: {e}")
                        st.code(traceback.format_exc(), language="python")

        st.divider()

        # ── Step 5: Report Agent ──────────────────────────────────────────────
        st.subheader("📄 Step 5 — Report Agent")
        if st.session_state.report_path:
            rpath = Path(st.session_state.report_path)
            if rpath.exists():
                content = rpath.read_text(encoding="utf-8")
                with st.expander("보고서 미리보기", expanded=True):
                    st.markdown(content)
                st.download_button("⬇️ 보고서 다운로드 (.md)", data=content,
                                   file_name=rpath.name, mime="text/markdown")
            if st.button("🔄 보고서 재생성", key="regen_report"):
                st.session_state.report_path = None
                geo_log.clear()
                st.rerun()
        else:
            if not st.session_state.analysis_result:
                st.warning("먼저 Analysis Agent를 실행하세요.")
            else:
                if st.button("▶ 보고서 생성", type="primary", key="run_report"):
                    from geo_cli.agents.report_agent import ReportAgent
                    geo_log.clear()
                    try:
                        rpath = _run_with_live_log(
                            ReportAgent(api_key=_api_key, model=_model).run,
                            brief, st.session_state.analysis_result,
                        )
                        st.session_state.report_path = str(rpath)
                        st.rerun()
                    except Exception as e:
                        import traceback
                        st.error(f"오류: {e}")
                        st.code(traceback.format_exc(), language="python")


# ══════════════════════════════════════════════════════════════════════════════
# 페이지 3 — 데이터
# ══════════════════════════════════════════════════════════════════════════════
elif current_page == "📂 데이터":
    st.title("📂 저장된 데이터")

    from geo_cli.utils.file_io import (
        load_brief as _load_brief,
        list_briefs as _list_briefs,
        brief_display_title,
        list_artifacts,
        pipeline_status,
        _STAGE_KO,
    )

    brief_files = _list_briefs()

    # 현재 세션의 brief가 이미 저장되었지만 목록에 없으면 추가
    if st.session_state.get("brief"):
        _cur = st.session_state.brief
        _cur_path = DATA_DIR / f"brief_{_cur.brief_id}.json"
        if _cur_path.exists() and _cur_path not in brief_files:
            brief_files.insert(0, _cur_path)

    if not brief_files:
        st.info("저장된 브리프가 없습니다. 먼저 인터뷰를 완료하세요.")
    else:
        st.caption(f"총 {len(brief_files)}개 분석")

        for bf in brief_files:
            bid = bf.stem.replace("brief_", "")
            try:
                _brief = _load_brief(bid)
            except Exception as _load_err:
                st.warning(f"브리프 로드 실패 ({bf.name}): {_load_err}")
                continue

            title = brief_display_title(_brief)
            status = pipeline_status(bid)
            artifacts = list_artifacts(bid)
            done_count = sum(status.values())
            total_count = len(status)

            # ── 분석 카드 (expander)
            with st.expander(f"📊 {title}  ({done_count}/{total_count} 완료)", expanded=False):

                # 파이프라인 상태 표시
                status_cols = st.columns(total_count)
                for col, (stage, complete) in zip(status_cols, status.items()):
                    icon = "✅" if complete else "⬜"
                    col.markdown(f"{icon} {_STAGE_KO.get(stage, stage)}")

                # 작업 재개 버튼
                if st.button("📂 이 브리프로 작업 재개", key=f"resume_{bid}", type="primary"):
                    from geo_cli.agents.query_agent import load_queries
                    from geo_cli.agents.testing_agent import load_testing_result
                    from geo_cli.agents.analysis_agent import load_analysis

                    st.session_state.brief = _brief
                    st.session_state.chat = []
                    st.session_state.interview_done = False
                    st.session_state.brief_dict = None
                    st.session_state.query_result = None
                    st.session_state.testing_result = None
                    st.session_state.analysis_result = None
                    st.session_state.report_path = None

                    try: st.session_state.query_result    = load_queries(bid)
                    except FileNotFoundError: pass
                    try: st.session_state.testing_result  = load_testing_result(bid)
                    except FileNotFoundError: pass
                    try: st.session_state.analysis_result = load_analysis(bid)
                    except FileNotFoundError: pass
                    rp = DATA_DIR / f"report_{bid}.md"
                    if rp.exists(): st.session_state.report_path = str(rp)

                    st.session_state.page = "▶ 파이프라인"
                    st.success(f"✅ {_brief.subject.name} 로드 완료")
                    st.rerun()

                st.divider()

                # ── 산출물 파일 목록
                if not artifacts:
                    st.caption("산출물 파일이 없습니다.")
                else:
                    for art in artifacts:
                        file_col, view_col, dl_col = st.columns([4, 1, 1])
                        with file_col:
                            st.markdown(f"**{art.label}** — `{art.path.name}`")
                        with view_col:
                            _preview_key = f"preview_{bid}_{art.path.name}"
                            if st.button("👁", key=_preview_key, help="미리보기"):
                                st.session_state[f"show_{_preview_key}"] = not st.session_state.get(f"show_{_preview_key}", False)
                        with dl_col:
                            _raw = art.path.read_bytes()
                            st.download_button(
                                "⬇️", data=_raw, file_name=art.path.name,
                                key=f"dl_{bid}_{art.path.name}",
                                mime="application/octet-stream",
                            )

                        # 인라인 뷰어 (토글)
                        _preview_key = f"preview_{bid}_{art.path.name}"
                        if st.session_state.get(f"show_{_preview_key}", False):
                            try:
                                content = art.path.read_text(encoding="utf-8")
                                if art.path.suffix == ".json":
                                    st.json(json.loads(content))
                                elif art.path.suffix == ".md":
                                    st.markdown(content)
                                elif art.path.suffix == ".csv":
                                    import pandas as pd
                                    df = pd.read_csv(art.path, encoding="utf-8-sig")
                                    st.dataframe(df, use_container_width=True, height=300)
                                else:
                                    st.text(content[:5000])
                            except Exception as _e:
                                st.error(f"파일 읽기 오류: {_e}")


# ══════════════════════════════════════════════════════════════════════════════
# 페이지 4 — 프롬프트 편집
# ══════════════════════════════════════════════════════════════════════════════
elif current_page == "🔧 프롬프트 편집":
    st.title("🔧 프롬프트 편집")
    st.caption("변경 후 저장하면 이후 실행부터 즉시 적용됩니다.")

    PROMPT_LABELS = {
        "orchestrator": "Orchestrator — 인터뷰 에이전트",
        "query_agent":  "Query Agent — 쿼리 생성",
        "analysis":     "Analysis Agent — GEO 분석",
        "report":       "Report Agent — 보고서 생성",
    }

    sel = st.selectbox("편집할 프롬프트", list(PROMPT_LABELS.keys()),
                       format_func=lambda k: PROMPT_LABELS[k])
    current = get_prompt(sel)

    col_info, col_reset = st.columns([4, 1])
    col_info.caption(f"`prompts/{sel}.txt` — {len(current):,}자")
    if col_reset.button("↩️ 초기화"):
        save_prompt(sel, _load_default_prompts()[sel])
        st.success("초기값으로 복원됐습니다.")
        st.rerun()

    edited = st.text_area("프롬프트 내용", value=current, height=520,
                          key=f"edit_{sel}")

    col_s, col_d = st.columns([1, 3])
    with col_s:
        if st.button("💾 저장", type="primary", use_container_width=True):
            save_prompt(sel, edited)
            st.success("저장 완료")
    with col_d:
        if edited != current:
            st.warning(f"⚠️ 미저장 변경 ({abs(len(edited)-len(current))}자 차이)")


# ══════════════════════════════════════════════════════════════════════════════
# 페이지 5 — 설정
# ══════════════════════════════════════════════════════════════════════════════
elif current_page == "⚙️ 설정":
    st.title("⚙️ 설정")

    st.subheader("🔑 API 설정")
    col1, col2 = st.columns(2)
    with col1:
        new_key = st.text_input("Anthropic API Key", value=_api_key, type="password")
    with col2:
        _models = ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"]
        new_model = st.selectbox("모델", _models,
                                 index=_models.index(_model) if _model in _models else 0)
    if st.button("💾 저장", key="save_api"):
        if ENV_FILE.exists():
            set_key(str(ENV_FILE), "ANTHROPIC_API_KEY", new_key)
            set_key(str(ENV_FILE), "GEO_MODEL", new_model)
            st.success("✅ 저장 완료. 앱 재시작 후 적용됩니다.")
        else:
            st.error(".env 파일이 없습니다.")

    st.divider()
    st.subheader("🤖 ChatGPT DOM 셀렉터")
    st.caption("ChatGPT UI가 변경되면 여기서 업데이트하세요.")

    from geo_cli.agents import testing_agent as _ta
    SEL_VARS = {
        "입력창": "_SEL_INPUT",
        "전송 버튼": "_SEL_SEND",
        "중지 버튼": "_SEL_STOP",
        "응답 컨테이너": "_SEL_RESPONSE",
        "인용 URL": "_SEL_CITATION",
    }
    sel_file    = ROOT / "geo_cli" / "agents" / "testing_agent.py"
    sel_content = sel_file.read_text(encoding="utf-8")
    new_values: dict[str, tuple[str,str]] = {}

    for label, var in SEL_VARS.items():
        cur = getattr(_ta, var, "")
        nv  = st.text_input(label, value=cur, key=f"sel_{var}")
        if nv != cur:
            new_values[var] = (cur, nv)

    if new_values and st.button("💾 셀렉터 저장", type="primary"):
        content = sel_content
        for var, (old, new) in new_values.items():
            content = content.replace(f'"{old}"', f'"{new}"', 1)
        sel_file.write_text(content, encoding="utf-8")
        st.success("✅ 저장 완료. 앱 재시작 후 적용됩니다.")

    st.divider()
    st.subheader("📁 데이터 경로")
    st.code(str(DATA_DIR))
    n_files = len(list(DATA_DIR.glob("*.*"))) if DATA_DIR.exists() else 0
    st.caption(f"저장된 파일: {n_files}개")
