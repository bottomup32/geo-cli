"""Interview session management — wraps Anthropic streaming + sentinel detection."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

import anthropic

from backend.config import ANTHROPIC_API_KEY, GEO_MODEL

SENTINEL = "<INTERVIEW_COMPLETE>"


def _get_prompt(name: str) -> str:
    from backend.config import PROMPTS_DIR
    path = PROMPTS_DIR / f"{name}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    # Fallback to hardcoded defaults
    if name == "orchestrator":
        from geo_cli.orchestrator.prompts import SYSTEM_PROMPT
        return SYSTEM_PROMPT
    return ""


@dataclass
class InterviewSession:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    messages: list[dict] = field(default_factory=list)
    interview_done: bool = False
    brief_dict: dict | None = None


class InterviewService:
    """Manages interview sessions (in-memory, single-user)."""

    def __init__(self):
        self._sessions: dict[str, InterviewSession] = {}

    def get_or_create(self, session_id: str | None = None) -> InterviewSession:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        session = InterviewSession(session_id=session_id or uuid.uuid4().hex[:12])
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> InterviewSession | None:
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str):
        self._sessions.pop(session_id, None)

    async def send_message_streaming(self, session: InterviewSession, user_text: str):
        """Send user message, yield streaming tokens. Detects sentinel."""
        api_key = ANTHROPIC_API_KEY
        model = GEO_MODEL

        if not api_key:
            yield {"type": "error", "message": "API 키가 설정되지 않았습니다."}
            return

        # Add opening message on first interaction
        if not session.messages:
            from geo_cli.orchestrator.prompts import OPENING_MESSAGE
            session.messages.append({"role": "assistant", "content": OPENING_MESSAGE})
            yield {"type": "opening", "content": OPENING_MESSAGE}

        session.messages.append({"role": "user", "content": user_text})

        client = anthropic.Anthropic(api_key=api_key, timeout=60.0)
        messages = [{"role": m["role"], "content": m["content"]} for m in session.messages]

        full_response = ""
        visible_text = ""
        sentinel_hit = False

        try:
            with client.messages.stream(
                model=model,
                max_tokens=4096,
                system=_get_prompt("orchestrator"),
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
                            yield {"type": "token", "content": chunk}

            # Save assistant message (visible part only)
            if not visible_text:
                visible_text = full_response
            session.messages.append({"role": "assistant", "content": visible_text})

            yield {"type": "complete", "content": visible_text}

            # Parse brief JSON if sentinel detected
            if sentinel_hit:
                _, json_part = full_response.split(SENTINEL, 1)
                json_str = json_part.strip()
                if json_str.startswith("```"):
                    lines = json_str.splitlines()
                    json_str = "\n".join(
                        lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                    ).strip()
                start = json_str.find("{")
                obj, _ = json.JSONDecoder().raw_decode(json_str, start)
                session.brief_dict = obj
                session.interview_done = True
                yield {"type": "interview_complete", "brief_dict": obj}

        except anthropic.APIStatusError as e:
            yield {"type": "error", "message": f"API 오류: {e}"}
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
            yield {"type": "error", "message": f"API 연결 오류: {e}"}
        except (ValueError, json.JSONDecodeError) as e:
            yield {"type": "error", "message": f"JSON 파싱 오류: {e}. 계속 대화하세요."}
        except Exception as e:
            yield {"type": "error", "message": f"예상치 못한 오류: {e}"}


# Global singleton
interview_service = InterviewService()
