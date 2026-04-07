"""
ElevenLabs TTS 기반 JS speak() 함수 생성기.
모든 페이지/컴포넌트의 접근성 낭독에 공통으로 사용한다.

- 성공 시: ElevenLabs API 호출 → MP3 재생
- 실패 시: 브라우저 Web Speech API 폴백
"""

from __future__ import annotations

import json
import os

import streamlit as st

_DEFAULT_SERVER = os.getenv('LLM_SERVER_URL', 'http://localhost:8000')


def get_server_url() -> str:
    """현재 프런트엔드가 호출할 백엔드 서버 주소를 반환한다."""
    return os.getenv('LLM_SERVER_URL', _DEFAULT_SERVER).rstrip('/')


def get_selected_voice(default: str = 'JiYeong Kang') -> str:
    """세션에 저장된 현재 선택 화자명을 반환한다."""
    return str(st.session_state.get('selected_voice', default))


def js_string(value: str) -> str:
    """JS 문자열 리터럴로 안전하게 넣기 위한 JSON 인코딩."""
    return json.dumps(value, ensure_ascii=False)


def make_speak_fn(
    voice_name: str | None = None,
    server_url: str | None = None,
    allow_generation: bool = False,
) -> str:
    """
    ElevenLabs TTS를 사용하는 JS speak(t, cb) 함수 코드를 반환한다.

    반환값은 <script> 블록 안에 직접 삽입할 수 있는 plain string이다.
    f-string 템플릿 안에서는 {make_speak_fn(voice)} 로 삽입한다.

    Args:
        voice_name: ElevenLabs 화자 이름 (session_state.selected_voice)
        server_url: FastAPI 서버 주소

    Returns:
        str: JS 함수 정의 코드
    """
    resolved_voice = voice_name or get_selected_voice()
    resolved_server = (server_url or get_server_url()).rstrip('/')
    voice_js = js_string(resolved_voice)
    server_js = js_string(resolved_server)
    return (
        f"  if (!window.currentAudio) window.currentAudio = null;\n"
        f"  async function speak(t, cb) {{\n"
        f"    if (!t) {{ if (cb) cb(); return; }}\n"
        f"    const done = () => {{ if (cb) cb(); }};\n"
        f"    \n"
        f"    // 1. 기존 재생 중인 오디오/TTS 중지\n"
        f"    if (window.currentAudio) {{\n"
        f"        window.currentAudio.pause();\n"
        f"        window.currentAudio.src = '';\n"
        f"        window.currentAudio = null;\n"
        f"    }}\n"
        f"    if (window.speechSynthesis) window.speechSynthesis.cancel();\n"
        f"    \n"
        f"    try {{\n"
        f"      const resp = await fetch({server_js} + '/api/tts/speak', {{\n"
        f"        method: 'POST',\n"
        f"        headers: {{'Content-Type': 'application/json'}},\n"
        f"        body: JSON.stringify({{text: t, voice_name: {voice_js}, allow_generation: {'true' if allow_generation else 'false'}}})\n"
        f"      }});\n"
        f"      if (!resp.ok) throw new Error('TTS ' + resp.status);\n"
        f"      const blob = await resp.blob();\n"
        f"      const url = URL.createObjectURL(blob);\n"
        f"      const audio = new Audio(url);\n"
        f"      window.currentAudio = audio; // 전역 저장\n"
        f"      \n"
        f"      audio.onended = () => {{ \n"
        f"        URL.revokeObjectURL(url); \n"
        f"        if (window.currentAudio === audio) window.currentAudio = null;\n"
        f"        done(); \n"
        f"      }};\n"
        f"      audio.onerror = () => {{ \n"
        f"        URL.revokeObjectURL(url); \n"
        f"        if (window.currentAudio === audio) window.currentAudio = null;\n"
        f"        done(); \n"
        f"      }};\n"
        f"      await audio.play();\n"
        f"    }} catch (e) {{\n"
        f"      console.warn('ElevenLabs speak 실패, 폴백:', e);\n"
        f"      if (!window.speechSynthesis) {{ done(); return; }}\n"
        f"      const u = new SpeechSynthesisUtterance(t);\n"
        f"      u.lang = 'ko-KR';\n"
        f"      u.rate = 1.0;\n"
        f"      u.onend = done;\n"
        f"      u.onerror = done;\n"
        f"      window.speechSynthesis.speak(u);\n"
        f"    }}\n"
        f"  }}"
    )
