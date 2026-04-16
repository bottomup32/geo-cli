"""AI Testing Agent — ChatGPT.com 쿼리 실행 (Playwright 스크래핑)"""
from __future__ import annotations

import csv
import json
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import TYPE_CHECKING

from geo_cli.orchestrator.schema import AnalysisBrief
from geo_cli.agents.query_agent import GeoQuery, QueryResult, load_queries
from geo_cli.ui.console import (
    console,
    print_separator,
    print_status,
    prompt_user,
    render_error_panel,
)

# ---------------------------------------------------------------------------
# ChatGPT.com DOM 셀렉터 (UI 변경 시 이 상수만 수정)
# ---------------------------------------------------------------------------

_CHATGPT_URL = "https://chatgpt.com/"

# 입력창 (contenteditable div)
_SEL_INPUT = "#prompt-textarea"

# 전송 버튼
_SEL_SEND = "[data-testid='send-button']"

# 스트리밍 중지 버튼 (응답 생성 중에만 표시)
_SEL_STOP = "[data-testid='stop-button']"

# assistant 메시지 컨테이너
_SEL_RESPONSE = "[data-message-author-role='assistant']"

# 응답 내 인용 URL 링크
_SEL_CITATION = "[data-message-author-role='assistant'] a[href]"

# ── 로그인 감지: 다중 시그널 방식 ──────────────────────────────────────────
# 비로그인 시 보이는 요소 (하나라도 있으면 NOT logged in)
_SEL_NOT_LOGGED_IN = [
    "button:has-text('Log in')",
    "button:has-text('Sign up')",
    "button:has-text('로그인')",
    "button:has-text('가입')",
    "[data-testid='login-button']",
    "a[href*='/auth/login']",
]

# 로그인 시 보이는 요소 (하나라도 있으면 logged in)
_SEL_LOGGED_IN_SIGNALS = [
    "[data-testid='profile-button']",
    "button[aria-label='User menu']",
    "img[alt='User']",
    "button[aria-label='My profile']",
    "[data-testid='SidebarHeader'] button:has(img)",
]

# ── 웹검색 토글 ───────────────────────────────────────────────────────────
_SEL_SEARCH_TOGGLE = "[data-testid='search-toggle']"
_SEL_SEARCH_TOGGLE_ALT = "button[aria-label*='earch']"
_SEL_SEARCH_ICON = "button[aria-label*='Search']"

_MAX_RETRIES = 2
_RESPONSE_TIMEOUT_MS = 120_000   # 2분 (긴 응답 고려)
_STREAM_POLL_INTERVAL = 1.5      # 스트리밍 완료 확인 간격 (초)
_STREAM_STABLE_WAIT = 2.0        # 스트리밍 완료 후 추가 대기


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RawResponse:
    query_id: str
    query_text: str
    platform: str
    response_text: str
    response_urls: list[str] = field(default_factory=list)
    timestamp: str = ""
    status: str = "success"   # "success" | "error" | "skipped"
    error_message: str = ""


@dataclass
class TestingResult:
    brief_id: str
    platform: str
    responses: list[RawResponse] = field(default_factory=list)
    total: int = 0
    success: int = 0
    error: int = 0

    def to_dict(self) -> dict:
        return {
            "brief_id": self.brief_id,
            "platform": self.platform,
            "total": self.total,
            "success": self.success,
            "error": self.error,
            "responses": [asdict(r) for r in self.responses],
        }


# ---------------------------------------------------------------------------
# ChatGPT scraper
# ---------------------------------------------------------------------------

def _get_profile_dir() -> Path:
    profile_dir = Path(os.getenv("GEO_CHATGPT_PROFILE_DIR", "")).expanduser()
    if not str(profile_dir):
        profile_dir = Path.home() / ".geo_cli" / "chatgpt_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


class ChatGPTScraper:
    """Playwright 기반 ChatGPT.com 스크래퍼."""

    def __init__(self, headless: bool = False):
        self._headless = headless
        self._browser = None
        self._context = None
        self._page = None
        self._pw = None

    def start(self) -> None:
        import sys
        import asyncio
        from playwright.sync_api import sync_playwright
        from geo_cli.utils.stream_log import geo_log

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        geo_log.info("Playwright 브라우저 시작 중...")
        self._pw = sync_playwright().start()

        geo_log.info("ChatGPT 테스트용 Chromium 창을 엽니다. 창이 보이지 않으면 작업 표시줄 또는 Alt+Tab을 확인하세요.")
        profile_dir = _get_profile_dir()
        geo_log.info(f"ChatGPT 로그인 전용 프로필 사용: {profile_dir}")
        self._context = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self._headless,
            viewport={"width": 1280, "height": 900},
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
            ignore_default_args=["--enable-automation"],
        )
        # 모든 페이지에 webdriver 플래그 숨김 적용
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        self._page.bring_to_front()
        geo_log.ok("브라우저 준비 완료")

    def stop(self) -> None:
        # Persistent context가 쿠키/로컬스토리지/로그인 상태를 프로필 폴더에 저장한다.
        if self._context:
            self._context.close()
        if self._pw:
            self._pw.stop()

    def navigate_and_wait_for_login(self) -> None:
        """ChatGPT.com으로 이동 후 로그인 + 웹검색 활성화를 확인한다."""
        from geo_cli.utils.stream_log import geo_log

        geo_log.info(f"ChatGPT.com 접속 중: {_CHATGPT_URL}")
        self._page.goto(_CHATGPT_URL)
        self._page.bring_to_front()
        self._page.wait_for_load_state("domcontentloaded", timeout=20_000)
        time.sleep(2.0)  # 페이지 안정화 대기
        geo_log.info("페이지 로드 완료 — 로그인 상태 확인 중...")

        # 이미 로그인된 경우
        if self._is_logged_in():
            geo_log.ok("이미 로그인되어 있습니다.")
            self._ensure_websearch_enabled()
            return

        # 로그인 필요 — 사용자에게 안내 후 자동 감지
        geo_log.warn("⚠ 로그인이 필요합니다. 브라우저 창에서 ChatGPT에 로그인하세요.")
        geo_log.info("로그인 완료를 자동으로 감지합니다 (최대 5분)...")

        start_time = time.time()
        deadline = start_time + 300  # 5분

        while time.time() < deadline:
            time.sleep(3.0)
            if self._is_logged_in():
                geo_log.ok("로그인 확인됨!")
                geo_log.info("로그인 상태가 전용 브라우저 프로필에 저장됩니다. 다음 실행부터 자동으로 재사용합니다.")
                self._ensure_websearch_enabled()
                return
            elapsed = int(time.time() - start_time)
            geo_log.info(f"로그인 대기 중... ({elapsed}초 경과)")

        raise RuntimeError("ChatGPT 로그인 타임아웃 (5분 초과)")

    def _is_logged_in(self) -> bool:
        """로그인 상태를 판단한다.
        전략:
          1. "Log in" / "Sign up" 버튼이 있으면 → 미로그인
          2. 양성 시그널(프로필 버튼 등)이 있으면 → 로그인
          3. 둘 다 없지만 입력창이 있으면 → 로그인으로 간주 (fallback)
        """
        from geo_cli.utils.stream_log import geo_log

        # 1. 비로그인 시그널 체크
        for sel in _SEL_NOT_LOGGED_IN:
            try:
                if self._page.locator(sel).count() > 0:
                    geo_log.info(f"비로그인 감지: {sel}")
                    return False
            except Exception:
                continue

        # 2. 양성 시그널 체크
        for sel in _SEL_LOGGED_IN_SIGNALS:
            try:
                if self._page.locator(sel).count() > 0:
                    geo_log.info(f"로그인 확인: {sel}")
                    return True
            except Exception:
                continue

        # 3. Fallback: 입력창 존재 + 비로그인 버튼 없음 → 로그인으로 간주
        try:
            if self._page.locator(_SEL_INPUT).count() > 0:
                geo_log.info("로그인 확인 (fallback): 입력창 존재 + 비로그인 버튼 없음")
                return True
        except Exception:
            pass

        return False

    def _ensure_websearch_enabled(self) -> None:
        """웹검색 토글이 비활성이면 활성화한다."""
        from geo_cli.utils.stream_log import geo_log
        geo_log.info("웹검색 토글 상태 확인 중...")

        # 새 채팅 페이지로 이동 (composer 컨트롤 접근)
        self._page.goto(_CHATGPT_URL)
        self._page.wait_for_selector(_SEL_INPUT, timeout=10_000)
        time.sleep(1.5)

        # 토글 찾기 (여러 셀렉터 시도)
        toggle = None
        for sel in [_SEL_SEARCH_TOGGLE, _SEL_SEARCH_TOGGLE_ALT, _SEL_SEARCH_ICON]:
            loc = self._page.locator(sel)
            if loc.count() > 0:
                toggle = loc.first
                break

        if toggle is None:
            geo_log.warn("웹검색 토글을 찾을 수 없습니다. ChatGPT 기본 설정을 사용합니다.")
            return

        # 활성 상태 확인
        aria_checked = toggle.get_attribute("aria-checked") or ""
        data_state = toggle.get_attribute("data-state") or ""
        is_on = aria_checked == "true" or data_state == "checked"

        if is_on:
            geo_log.ok("웹검색이 이미 활성화되어 있습니다.")
        else:
            geo_log.info("웹검색 토글 활성화 중...")
            try:
                toggle.click()
                time.sleep(1.0)
                geo_log.ok("웹검색 토글 활성화 완료.")
            except Exception as e:
                geo_log.warn(f"웹검색 토글 클릭 실패: {e}. 수동으로 활성화해 주세요.")

    def _validate_websearch(self) -> bool:
        """테스트 쿼리로 웹검색이 URL을 반환하는지 검증한다."""
        from geo_cli.utils.stream_log import geo_log
        geo_log.info("웹검색 검증 중 (테스트 쿼리 실행)...")

        test_query = "What are the latest technology news today? Please include source links."
        try:
            response_text, urls = self.query(test_query)
            if urls:
                geo_log.ok(f"웹검색 검증 성공 — {len(urls)}개 참조 URL 확인됨")
                return True
            else:
                geo_log.warn("웹검색 검증: 참조 URL이 없습니다. 응답에 웹 링크가 포함되지 않을 수 있습니다.")
                return False
        except Exception as e:
            geo_log.warn(f"웹검색 검증 중 오류: {e}")
            return False

    def query(self, query_text: str) -> tuple[str, list[str]]:
        """
        새 채팅을 시작하고 query_text를 전송한다.
        Returns: (response_text, cited_urls)
        """
        # 새 채팅 페이지로 이동 (이전 대화 컨텍스트 제거)
        self._page.goto(_CHATGPT_URL)
        self._page.wait_for_selector(_SEL_INPUT, timeout=15_000)
        time.sleep(1.0)  # 페이지 안정화 대기

        # 입력창에 텍스트 입력
        input_el = self._page.locator(_SEL_INPUT)
        input_el.click()
        input_el.fill(query_text)
        time.sleep(0.3)

        # 전송
        send_btn = self._page.locator(_SEL_SEND)
        send_btn.click()

        # 스트리밍 완료 대기
        self._wait_for_response_complete()

        # 응답 텍스트 추출 (마지막 assistant 메시지)
        response_text = self._extract_last_response()
        cited_urls = self._extract_citations()

        return response_text, cited_urls

    def _wait_for_response_complete(self) -> None:
        """
        응답 스트리밍이 완료될 때까지 기다린다.
        전략: stop 버튼이 나타났다가 사라지는 것을 감지.
        """
        deadline = time.time() + (_RESPONSE_TIMEOUT_MS / 1000)

        # 1. stop 버튼 등장 대기 (스트리밍 시작)
        stop_appeared = False
        while time.time() < deadline:
            stop = self._page.locator(_SEL_STOP)
            if stop.count() > 0:
                stop_appeared = True
                break
            time.sleep(0.5)

        if not stop_appeared:
            # stop 버튼 없이 바로 응답이 완료된 경우 (짧은 응답 등)
            time.sleep(_STREAM_STABLE_WAIT)
            return

        # 2. stop 버튼 소멸 대기 (스트리밍 완료)
        while time.time() < deadline:
            stop = self._page.locator(_SEL_STOP)
            if stop.count() == 0:
                break
            time.sleep(_STREAM_POLL_INTERVAL)

        # 3. 추가 안정화 대기 (DOM 갱신 여유)
        time.sleep(_STREAM_STABLE_WAIT)

    def _extract_last_response(self) -> str:
        """마지막 assistant 메시지 텍스트를 추출한다."""
        responses = self._page.locator(_SEL_RESPONSE)
        count = responses.count()
        if count == 0:
            return ""
        # inner_text()는 마크다운 렌더링 후 텍스트
        return responses.nth(count - 1).inner_text()

    def _extract_citations(self) -> list[str]:
        """assistant 메시지 내 href 링크를 수집한다."""
        links = self._page.locator(_SEL_CITATION)
        urls = []
        for i in range(links.count()):
            href = links.nth(i).get_attribute("href")
            if href and href.startswith("http"):
                urls.append(href)
        return list(dict.fromkeys(urls))  # 중복 제거, 순서 유지


# ---------------------------------------------------------------------------
# Testing Agent
# ---------------------------------------------------------------------------

class TestingAgent:
    def __init__(self):
        self._scraper = ChatGPTScraper(headless=False)
        self.login_event: threading.Event | None = None   # Streamlit에서 주입 가능

    def run(self, brief: AnalysisBrief, query_result: QueryResult | None = None) -> TestingResult:
        from geo_cli.utils.stream_log import geo_log
        geo_log.step("Testing Agent 시작 — ChatGPT.com")

        print_separator()
        console.print("\n[bold cyan]▶ AI Testing Agent[/] — ChatGPT.com\n")

        # 쿼리 로드
        if query_result is None:
            try:
                query_result = load_queries(brief.brief_id)
            except FileNotFoundError:
                render_error_panel(
                    "쿼리 파일 없음",
                    f"data/queries_{brief.brief_id}.json 파일이 필요합니다."
                )
                raise

        queries = query_result.queries
        from geo_cli.utils.stream_log import geo_log
        geo_log.info(f"총 {len(queries)}개 쿼리 실행 예정")
        print_status(f"총 {len(queries)}개 쿼리 → ChatGPT.com 실행 예정")
        print_status("브라우저 창이 열립니다. 로그인 후 진행됩니다.")

        result = TestingResult(
            brief_id=brief.brief_id,
            platform="chatgpt",
            total=len(queries),
        )

        try:
            self._scraper.start()
            self._scraper.navigate_and_wait_for_login()

            # 웹검색 작동 검증 (URL 수집 가능 여부)
            if not self._scraper._validate_websearch():
                from geo_cli.utils.stream_log import geo_log as _wgl
                _wgl.warn("웹검색이 비활성 상태일 수 있습니다. 쿼리 응답에 참조 URL이 누락될 수 있습니다.")

            from geo_cli.utils.stream_log import geo_log as _gl
            _gl.info(f"{len(queries)}개 쿼리 순서대로 실행 시작...")
            result.responses = self._run_queries(queries, brief.brief_id)
            result.success = sum(1 for r in result.responses if r.status == "success")
            result.error = sum(1 for r in result.responses if r.status == "error")

        except KeyboardInterrupt:
            console.print("\n[geo.warn]⚠ 사용자가 중단했습니다. 지금까지 수집된 결과를 저장합니다.[/]")
        finally:
            self._scraper.stop()

        # 저장
        json_path, csv_path = _save_testing_result(result, brief.brief_id)
        console.print(f"\n[geo.success]✓[/] 완료: 성공 {result.success} / 오류 {result.error} / 전체 {result.total}")
        console.print(f"  [geo.hint]JSON: {json_path}[/]")
        console.print(f"  [geo.hint]CSV:  {csv_path}[/]")
        print_separator()

        return result

    def _run_queries(self, queries: list[GeoQuery], brief_id: str) -> list[RawResponse]:
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        import datetime

        responses: list[RawResponse] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task("ChatGPT 쿼리 실행 중...", total=len(queries))

            for i, q in enumerate(queries):
                progress.update(task, description=f"[{q.id}] {q.text[:40]}...")
                from geo_cli.utils.stream_log import geo_log
                geo_log.info(f"[{i+1}/{len(queries)}] {q.id}: {q.text[:60]}")

                raw = self._execute_with_retry(q)
                raw.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                if raw.status == "success":
                    from geo_cli.utils.stream_log import geo_log as gl
                    gl.ok(f"{q.id} 완료 — 응답 {len(raw.response_text)}자, URL {len(raw.response_urls)}개")
                else:
                    from geo_cli.utils.stream_log import geo_log as gl
                    gl.error(f"{q.id} 실패 — {raw.error_message}")
                responses.append(raw)

                # 중간 저장 (크래시 대비)
                _autosave_progress(responses, brief_id)

                progress.advance(task)
                time.sleep(1.5)  # 요청 간 간격 (봇 감지 방지)

        return responses

    def _execute_with_retry(self, q: GeoQuery) -> RawResponse:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response_text, urls = self._scraper.query(q.text)
                return RawResponse(
                    query_id=q.id,
                    query_text=q.text,
                    platform="chatgpt",
                    response_text=response_text,
                    response_urls=urls,
                    status="success",
                )
            except Exception as e:
                if attempt < _MAX_RETRIES:
                    console.print(f"  [geo.warn]재시도 {attempt + 1}/{_MAX_RETRIES}: {q.id}[/]")
                    time.sleep(3.0)
                else:
                    console.print(f"  [geo.error]실패 (스킵): {q.id} — {e}[/]")
                    return RawResponse(
                        query_id=q.id,
                        query_text=q.text,
                        platform="chatgpt",
                        response_text="",
                        status="error",
                        error_message=str(e),
                    )
        # unreachable
        raise RuntimeError


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _save_testing_result(
    result: TestingResult,
    brief_id: str,
    data_dir: Path | None = None,
) -> tuple[Path, Path]:
    from geo_cli.utils.file_io import _ensure_data_dir, _DEFAULT_DATA_DIR, atomic_write
    target_dir = _ensure_data_dir(data_dir or _DEFAULT_DATA_DIR)

    json_path = target_dir / f"raw_chatgpt_{brief_id}.json"
    atomic_write(json_path, json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    csv_path = target_dir / f"raw_chatgpt_{brief_id}.csv"
    _write_csv(csv_path, result.responses)

    return json_path, csv_path


def _autosave_progress(responses: list[RawResponse], brief_id: str) -> None:
    """실행 도중 중간 저장 (크래시 대비)."""
    from geo_cli.utils.file_io import _DEFAULT_DATA_DIR, atomic_write
    path = _DEFAULT_DATA_DIR / f"raw_chatgpt_{brief_id}.partial.json"
    try:
        atomic_write(
            path,
            json.dumps(
                {"brief_id": brief_id, "responses": [asdict(r) for r in responses]},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception:
        pass  # autosave 실패는 무시


def load_testing_result(brief_id: str, platform: str = "chatgpt", data_dir: Path | None = None) -> TestingResult:
    from geo_cli.utils.file_io import _DEFAULT_DATA_DIR
    target_dir = data_dir or _DEFAULT_DATA_DIR
    json_path = target_dir / f"raw_{platform}_{brief_id}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"테스트 결과 파일 없음: {json_path}")
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    responses = [
        RawResponse(
            query_id=r["query_id"],
            query_text=r["query_text"],
            platform=r["platform"],
            response_text=r["response_text"],
            response_urls=r.get("response_urls", []),
            timestamp=r.get("timestamp", ""),
            status=r.get("status", "success"),
            error_message=r.get("error_message", ""),
        )
        for r in data["responses"]
    ]
    return TestingResult(
        brief_id=data["brief_id"],
        platform=data["platform"],
        responses=responses,
        total=data["total"],
        success=data["success"],
        error=data["error"],
    )


def _write_csv(path: Path, responses: list[RawResponse]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "query_id", "query_text", "platform",
                "response_text", "response_urls",
                "timestamp", "status", "error_message",
            ],
        )
        writer.writeheader()
        for r in responses:
            row = asdict(r)
            row["response_urls"] = "; ".join(r.response_urls)
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Module-level entry point (called from main.py)
# ---------------------------------------------------------------------------

def run(brief: AnalysisBrief, query_result: QueryResult | None = None) -> TestingResult:
    agent = TestingAgent()
    return agent.run(brief, query_result)
