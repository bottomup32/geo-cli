"""Settings API router."""
from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import set_key
from fastapi import APIRouter

from backend.config import DATA_DIR, ENV_FILE, PROMPTS_DIR, ROOT
from backend.schemas.api_models import (
    SelectorsUpdateRequest,
    SettingsResponse,
    SettingsUpdateRequest,
)

router = APIRouter()

_SEL_VARS = {
    "입력창": "_SEL_INPUT",
    "전송 버튼": "_SEL_SEND",
    "중지 버튼": "_SEL_STOP",
    "응답 컨테이너": "_SEL_RESPONSE",
    "인용 URL": "_SEL_CITATION",
}


def _read_selectors() -> dict[str, str]:
    sel_file = ROOT / "geo_cli" / "agents" / "testing_agent.py"
    if not sel_file.exists():
        return {}
    content = sel_file.read_text(encoding="utf-8")
    result = {}
    for label, var in _SEL_VARS.items():
        match = re.search(rf'^{var}\s*=\s*"(.+?)"', content, re.MULTILINE)
        if match:
            result[label] = match.group(1)
    return result


@router.get("", response_model=SettingsResponse)
def get_settings():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("GEO_MODEL", "claude-sonnet-4-6")
    profile_dir = os.getenv("GEO_CHATGPT_PROFILE_DIR", "~/.geo_cli/chatgpt_profile")
    return SettingsResponse(
        api_key_set=bool(api_key),
        api_key_preview=f"...{api_key[-8:]}" if len(api_key) > 8 else ("설정됨" if api_key else ""),
        model=model,
        data_dir=str(DATA_DIR),
        chatgpt_profile_dir=str(Path(profile_dir).expanduser()),
        selectors=_read_selectors(),
    )


@router.put("")
def update_settings(req: SettingsUpdateRequest):
    if not ENV_FILE.exists():
        ENV_FILE.write_text("", encoding="utf-8")
    if req.api_key is not None:
        set_key(str(ENV_FILE), "ANTHROPIC_API_KEY", req.api_key)
        os.environ["ANTHROPIC_API_KEY"] = req.api_key
    if req.model is not None:
        set_key(str(ENV_FILE), "GEO_MODEL", req.model)
        os.environ["GEO_MODEL"] = req.model
    if req.chatgpt_profile_dir is not None:
        profile_dir = req.chatgpt_profile_dir.strip()
        set_key(str(ENV_FILE), "GEO_CHATGPT_PROFILE_DIR", profile_dir)
        os.environ["GEO_CHATGPT_PROFILE_DIR"] = profile_dir
    return {"status": "ok"}


@router.get("/selectors")
def get_selectors():
    return _read_selectors()


@router.put("/selectors")
def update_selectors(req: SelectorsUpdateRequest):
    sel_file = ROOT / "geo_cli" / "agents" / "testing_agent.py"
    if not sel_file.exists():
        return {"error": "testing_agent.py not found"}

    content = sel_file.read_text(encoding="utf-8")
    for label, new_val in req.selectors.items():
        var = _SEL_VARS.get(label)
        if var:
            escaped_val = new_val.replace("\\", "\\\\").replace('"', '\\"')
            content = re.sub(
                rf'^({var}\s*=\s*")(.+?)(")',
                lambda match, val=escaped_val: f"{match.group(1)}{val}{match.group(3)}",
                content,
                flags=re.MULTILINE,
            )
    sel_file.write_text(content, encoding="utf-8")
    return {"status": "ok"}
