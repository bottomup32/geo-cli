"""
Orchestrator Agent — 상태 머신 기반 인터뷰 에이전트
"""
from __future__ import annotations

import json
import sys
from enum import Enum, auto
from pathlib import Path
from typing import Generator

import anthropic

from geo_cli.orchestrator.prompts import SYSTEM_PROMPT, OPENING_MESSAGE
from geo_cli.orchestrator.schema import AnalysisBrief
from geo_cli.ui.console import (
    console,
    render_welcome_panel,
    render_confirmation_table,
    render_success_panel,
    render_error_panel,
    render_interrupt_panel,
    prompt_user,
    print_agent_label,
    print_separator,
    print_status,
)
from geo_cli.utils.file_io import save_brief

SENTINEL = "<INTERVIEW_COMPLETE>"
MAX_TURNS = 30


class State(Enum):
    WELCOME = auto()
    GATHERING = auto()
    CONFIRMATION = auto()
    SAVING = auto()
    DONE = auto()
    ERROR = auto()


class OrchestratorAgent:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._messages: list[dict] = []
        self._state = State.WELCOME
        self._turn_count = 0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> AnalysisBrief:
        """인터뷰를 실행하고 승인된 AnalysisBrief를 반환한다."""
        try:
            return self._run_loop()
        except KeyboardInterrupt:
            self._handle_interrupt()
            sys.exit(0)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> AnalysisBrief:
        # WELCOME
        render_welcome_panel()
        input()  # Enter 대기
        print_separator()

        # Opening message from agent
        self._print_opening()

        # GATHERING loop
        self._state = State.GATHERING
        brief_dict: dict | None = None

        while self._state == State.GATHERING:
            if self._turn_count >= MAX_TURNS:
                print_status("인터뷰가 너무 길어졌습니다. 지금까지 수집된 정보로 마무리합니다...")
                self._messages.append({
                    "role": "user",
                    "content": "지금까지 수집된 정보를 바탕으로 최대한 완성된 분석 브리프를 JSON 형식으로 출력해 주세요. 빠진 필드는 기본값을 사용하세요.",
                })

            user_input = prompt_user()
            if not user_input.strip():
                continue

            self._messages.append({"role": "user", "content": user_input})
            self._turn_count += 1

            response = self._call_claude_streaming()

            # Sentinel 감지
            if SENTINEL in response:
                brief_dict = self._extract_brief_json(response)
                if brief_dict:
                    self._state = State.CONFIRMATION
                else:
                    render_error_panel("JSON 파싱 실패", "다시 시도합니다...")
                    brief_dict = self._request_json_retry()
                    if brief_dict:
                        self._state = State.CONFIRMATION

        # CONFIRMATION
        if self._state == State.CONFIRMATION and brief_dict:
            brief = self._confirm(brief_dict)
            if brief is None:
                # 사용자가 재시작을 선택한 경우
                self._messages = []
                self._turn_count = 0
                self._state = State.GATHERING
                self._print_opening()
                return self._run_loop()
            self._state = State.SAVING
        else:
            raise RuntimeError("예상치 못한 상태: brief_dict가 없습니다.")

        # SAVING
        file_path = self._save(brief)
        render_success_panel(str(file_path))
        print_separator()
        return brief

    # ------------------------------------------------------------------
    # Opening
    # ------------------------------------------------------------------

    def _print_opening(self) -> None:
        print_agent_label()
        console.print(OPENING_MESSAGE)
        # Opening 메시지를 assistant 메시지로 기록 (다음 턴에 컨텍스트 유지용)
        self._messages.append({"role": "assistant", "content": OPENING_MESSAGE})

    # ------------------------------------------------------------------
    # Claude API call (streaming)
    # ------------------------------------------------------------------

    def _call_claude_streaming(self) -> str:
        print_agent_label()
        full_response = ""

        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=self._messages,
            ) as stream:
                for text in stream.text_stream:
                    # SENTINEL 이후 JSON 블록은 터미널에 출력하지 않음
                    if SENTINEL in (full_response + text):
                        if SENTINEL not in full_response:
                            # SENTINEL 직전까지만 출력
                            pre, _ = (full_response + text).split(SENTINEL, 1)
                            pre_new = pre[len(full_response):]
                            if pre_new:
                                print(pre_new, end="", flush=True)
                        full_response += text
                    else:
                        print(text, end="", flush=True)
                        full_response += text

        except anthropic.APIConnectionError as e:
            render_error_panel("API 연결 실패", f"ANTHROPIC_API_KEY를 확인하세요.\n{e}")
            sys.exit(1)
        except anthropic.APIStatusError as e:
            render_error_panel("API 오류", str(e))
            sys.exit(1)

        print()  # 줄바꿈

        # 응답을 대화 히스토리에 추가 (SENTINEL 이후 JSON 제외)
        display_response = full_response.split(SENTINEL)[0].strip() if SENTINEL in full_response else full_response
        self._messages.append({"role": "assistant", "content": full_response})

        return full_response

    # ------------------------------------------------------------------
    # JSON extraction
    # ------------------------------------------------------------------

    def _extract_brief_json(self, response: str) -> dict | None:
        """<INTERVIEW_COMPLETE> 이후의 JSON 블록을 추출하고 파싱한다."""
        try:
            _, json_part = response.split(SENTINEL, 1)
            json_str = json_part.strip()
            # 코드 펜스 제거 (```json ... ```)
            if json_str.startswith("```"):
                lines = json_str.splitlines()
                json_str = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                json_str = json_str.strip()
            # { 위치부터 raw_decode로 첫 번째 완전한 JSON 객체만 파싱
            # (JSON 뒤에 추가 텍스트가 있어도 안전하게 처리)
            start = json_str.find("{")
            if start == -1:
                raise ValueError("JSON 객체를 찾을 수 없습니다.")
            obj, _ = json.JSONDecoder().raw_decode(json_str, start)
            return obj
        except (ValueError, json.JSONDecodeError) as e:
            render_error_panel("JSON 파싱 실패", str(e))
            return None

    def _request_json_retry(self) -> dict | None:
        """JSON 파싱 실패 시 재시도 요청을 주입한다. 성공 시 dict 반환."""
        self._messages.append({
            "role": "user",
            "content": f"JSON 출력에 파싱 오류가 있었습니다. {SENTINEL} 이후에 올바른 JSON만 출력해 주세요. JSON 외 다른 텍스트는 추가하지 마세요.",
        })
        response = self._call_claude_streaming()
        if SENTINEL in response:
            brief_dict = self._extract_brief_json(response)
            if brief_dict:
                return brief_dict
        render_error_panel("재시도 후에도 JSON 파싱 실패", "인터뷰를 재시작합니다.")
        self._messages = []
        self._turn_count = 0
        return None

    # ------------------------------------------------------------------
    # Confirmation UX
    # ------------------------------------------------------------------

    def _confirm(self, brief_dict: dict) -> AnalysisBrief | None:
        print_separator()
        console.print("\n[bold cyan]수집된 정보를 확인해 주세요.[/]\n")
        render_confirmation_table(brief_dict)

        console.print(
            "\n[geo.hint]명령어: [geo.input]approve[/] (승인) | "
            "[geo.input]edit[/] (수정) | "
            "[geo.input]restart[/] (처음부터)[/]\n"
        )

        while True:
            raw = prompt_user("명령 입력").strip().lower()

            if raw in ("approve", "승인", "확인", "yes", "y"):
                brief = AnalysisBrief.from_dict(brief_dict)
                # 시스템이 채워야 할 필드 설정
                if not brief.brief_id:
                    from geo_cli.orchestrator.schema import _generate_brief_id
                    brief.brief_id = _generate_brief_id()
                from datetime import datetime, timezone
                if not brief.created_at:
                    brief.created_at = datetime.now(timezone.utc).isoformat()
                brief.status = "approved"
                brief.metadata.model_used = self._model
                brief.metadata.interview_turns = self._turn_count
                return brief

            elif raw.startswith("edit") or raw.startswith("수정"):
                edit_request = raw[4:].strip() if raw.startswith("edit") else raw[2:].strip()
                if not edit_request:
                    console.print("[geo.hint]어떤 부분을 수정하시겠어요?[/]")
                    edit_request = prompt_user()
                self._messages.append({
                    "role": "user",
                    "content": f"다음 부분을 수정해 주세요: {edit_request}. 수정 후 다시 <INTERVIEW_COMPLETE> JSON을 출력해 주세요.",
                })
                response = self._call_claude_streaming()
                if SENTINEL in response:
                    new_brief_dict = self._extract_brief_json(response)
                    if new_brief_dict:
                        brief_dict = new_brief_dict
                        print_separator()
                        console.print("\n[bold cyan]수정된 내용을 확인해 주세요.[/]\n")
                        render_confirmation_table(brief_dict)
                        console.print(
                            "\n[geo.hint]명령어: [geo.input]approve[/] | "
                            "[geo.input]edit[/] | "
                            "[geo.input]restart[/][/]\n"
                        )

            elif raw in ("restart", "재시작", "r"):
                return None

            else:
                console.print("[geo.hint]  approve / edit / restart 중 하나를 입력해 주세요.[/]")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self, brief: AnalysisBrief) -> Path:
        return save_brief(brief)

    # ------------------------------------------------------------------
    # Interrupt handler
    # ------------------------------------------------------------------

    def _handle_interrupt(self) -> None:
        console.print()
        if self._messages:
            # 현재까지의 대화를 draft로 저장
            try:
                draft_brief = AnalysisBrief.new()
                draft_brief.status = "draft"
                draft_brief.metadata.interview_turns = self._turn_count
                draft_brief.additional_context = f"[DRAFT — 인터뷰 중단됨. 대화 {self._turn_count}턴 완료]"
                file_path = save_brief(draft_brief)
                render_interrupt_panel(str(file_path))
            except Exception:
                render_interrupt_panel("저장 실패")
        else:
            console.print("\n[geo.hint]종료합니다.[/]")
