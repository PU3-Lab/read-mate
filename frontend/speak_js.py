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

_DEFAULT_SERVER = os.getenv('LLM_SERVER_URL', 'http://localhost:28765')


def get_server_url() -> str:
    """현재 프런트엔드가 호출할 백엔드 서버 주소를 반환한다."""
    return os.getenv('LLM_SERVER_URL', _DEFAULT_SERVER).rstrip('/')


def get_selected_voice(default: str = 'JiYeong Kang') -> str:
    """세션에 저장된 현재 선택 화자명을 반환한다."""
    return str(st.session_state.get('selected_voice', default))


def get_voice_speed(default: float = 1.0) -> float:
    """세션에 저장된 재생 속도를 반환한다."""
    return float(st.session_state.get('voice_speed', default))


def js_string(value: str) -> str:
    """JS 문자열 리터럴로 안전하게 넣기 위한 JSON 인코딩."""
    return json.dumps(value, ensure_ascii=False)


def get_announcement_token(screen_key: str) -> int:
    """현재 화면 키가 바뀔 때만 안내 토큰을 증가시킨다."""
    current_key = str(st.session_state.get('_a11y_screen_key', ''))
    if current_key != screen_key:
        st.session_state['_a11y_screen_key'] = screen_key
        st.session_state['_a11y_screen_token'] = (
            int(st.session_state.get('_a11y_screen_token', 0)) + 1
        )
    return int(st.session_state.get('_a11y_screen_token', 0))


def make_speak_fn(
    voice_name: str | None = None,
    server_url: str | None = None,
    allow_generation: bool = False,
    priority: str = 'normal',
    voice_speed: float | None = None,
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
    resolved_speed = voice_speed if voice_speed is not None else get_voice_speed()
    voice_js = js_string(resolved_voice)
    server_js = js_string(resolved_server)
    priority_js = js_string(priority)
    speed_js = str(round(resolved_speed, 2))
    return (
        f"  const __rmOwner = (() => {{\n"
        f"    try {{ return window.parent || window; }} catch (err) {{ return window; }}\n"
        f"  }})();\n"
        f"  if (!__rmOwner.__rmAudioState) {{\n"
        f"    __rmOwner.__rmAudioState = {{\n"
        f"      currentAudio: null,\n"
        f"      currentToken: 0,\n"
        f"      activePriority: 0,\n"
        f"      pendingController: null,\n"
        f"    }};\n"
        f"  }}\n"
        f"  if (!__rmOwner.__rmSpokenKeys) __rmOwner.__rmSpokenKeys = {{}};\n"
        f"  __rmOwner.__rmVoiceSpeed = {speed_js};\n"
        f"  function rmPriorityValue(level) {{\n"
        f"    if (level === 'summary') return 100;\n"
        f"    if (level === 'high') return 50;\n"
        f"    return 10;\n"
        f"  }}\n"
        f"  function stopSpeak(resetPriority = true) {{\n"
        f"    const state = __rmOwner.__rmAudioState;\n"
        f"    if (state.pendingController) {{\n"
        f"      try {{ state.pendingController.abort(); }} catch (err) {{}}\n"
        f"      state.pendingController = null;\n"
        f"    }}\n"
        f"    try {{\n"
        f"      const synth = __rmOwner.speechSynthesis || window.speechSynthesis;\n"
        f"      if (synth) synth.cancel();\n"
        f"    }} catch (err) {{}}\n"
        f"    const audio = state.currentAudio || __rmOwner.__rmCurrentAudio || null;\n"
        f"    if (audio) {{\n"
        f"      try {{ audio.pause(); }} catch (err) {{}}\n"
        f"      try {{ audio.currentTime = 0; }} catch (err) {{}}\n"
        f"      try {{ audio.src = ''; }} catch (err) {{}}\n"
        f"    }}\n"
        f"    state.currentAudio = null;\n"
        f"    __rmOwner.__rmCurrentAudio = null;\n"
        f"    if (resetPriority) {{\n"
        f"      state.activePriority = 0;\n"
        f"      state.currentToken = 0;\n"
        f"    }}\n"
        f"  }}\n"
        f"  function claimAudio(audio, priorityLevel, token) {{\n"
        f"    const state = __rmOwner.__rmAudioState;\n"
        f"    const current = state.currentAudio || __rmOwner.__rmCurrentAudio;\n"
        f"    if (current && current !== audio) {{\n"
        f"      try {{ current.pause(); }} catch (err) {{}}\n"
        f"      try {{ current.currentTime = 0; }} catch (err) {{}}\n"
        f"    }}\n"
        f"    try {{\n"
        f"      const synth = __rmOwner.speechSynthesis || window.speechSynthesis;\n"
        f"      if (synth) synth.cancel();\n"
        f"    }} catch (err) {{}}\n"
        f"    state.currentAudio = audio;\n"
        f"    state.activePriority = rmPriorityValue(priorityLevel);\n"
        f"    if (typeof token === 'number') state.currentToken = token;\n"
        f"    __rmOwner.__rmCurrentAudio = audio;\n"
        f"  }}\n"
        f"  function speakOnce(key, t, cb, opts) {{\n"
        f"    if (!key) {{ speak(t, cb, opts); return; }}\n"
        f"    if (__rmOwner.__rmSpokenKeys[key]) {{ if (cb) cb(); return; }}\n"
        f"    __rmOwner.__rmSpokenKeys[key] = true;\n"
        f"    speak(t, cb, opts);\n"
        f"  }}\n"
        f"  async function speak(t, cb, opts) {{\n"
        f"    if (!t) {{ if (cb) cb(); return; }}\n"
        f"    const options = opts || {{}};\n"
        f"    const priorityLevel = options.priority || {priority_js};\n"
        f"    const priorityValue = rmPriorityValue(priorityLevel);\n"
        f"    const state = __rmOwner.__rmAudioState;\n"
        f"    if (state.activePriority > priorityValue) {{ if (cb) cb(); return; }}\n"
        f"    const token = state.currentToken + 1;\n"
        f"    stopSpeak(false);\n"
        f"    state.currentToken = token;\n"
        f"    state.activePriority = priorityValue;\n"
        f"    const done = () => {{ if (cb) cb(); }};\n"
        f"    const finish = () => {{\n"
        f"      if (state.currentToken === token) {{\n"
        f"        state.pendingController = null;\n"
        f"        state.currentAudio = null;\n"
        f"        state.activePriority = 0;\n"
        f"        state.currentToken = 0;\n"
        f"        __rmOwner.__rmCurrentAudio = null;\n"
        f"      }}\n"
        f"      done();\n"
        f"    }};\n"
        f"    console.log('[Speak] 요청:', t.substring(0, 50) + '...', 'priority:', priorityLevel, 'token:', token);\n"
        f"    try {{\n"
        f"      const controller = new AbortController();\n"
        f"      state.pendingController = controller;\n"
        f"      const url = {server_js} + '/api/tts/speak';\n"
        f"      const resp = await fetch(url, {{\n"
        f"        method: 'POST',\n"
        f"        headers: {{'Content-Type': 'application/json'}},\n"
        f"        body: JSON.stringify({{text: t, voice_name: {voice_js}, allow_generation: {'true' if allow_generation else 'false'}}}),\n"
        f"        signal: controller.signal,\n"
        f"      }});\n"
        f"      if (!resp.ok) {{\n"
        f"        const txt = await resp.text();\n"
        f"        throw new Error(`TTS ${{resp.status}}: ${{txt}}`);\n"
        f"      }}\n"
        f"      if (state.currentToken !== token) return;\n"
        f"      const blob = await resp.blob();\n"
        f"      console.log('[Speak] Blob 수신 완료:', blob.size, 'bytes');\n"
        f"      const url_blob = URL.createObjectURL(blob);\n"
        f"      if (state.currentToken !== token) {{ URL.revokeObjectURL(url_blob); return; }}\n"
        f"      const audio = new Audio(url_blob);\n"
        f"      audio.playbackRate = __rmOwner.__rmVoiceSpeed || 1.0;\n"
        f"      claimAudio(audio, priorityLevel, token);\n"
        f"      audio.onended = () => {{ \n"
        f"        URL.revokeObjectURL(url_blob); \n"
        f"        if (__rmOwner.__rmCurrentAudio === audio) __rmOwner.__rmCurrentAudio = null;\n"
        f"        console.log('[Speak] 재생 종료');\n"
        f"        finish(); \n"
        f"      }};\n"
        f"      audio.onerror = (e) => {{ \n"
        f"        if (audio.src === '' || audio.src === window.location.href) return; // 의도적 중단\n"
        f"        const err = audio.error;\n"
        f"        console.error('[Speak] 오디오 재생 오류:', err ? `Code: ${{err.code}}, Message: ${{err.message}}` : '알 수 없는 오류', e);\n"
        f"        URL.revokeObjectURL(url_blob); \n"
        f"        if (__rmOwner.__rmCurrentAudio === audio) __rmOwner.__rmCurrentAudio = null;\n"
        f"        finish(); \n"
        f"      }};\n"
        f"      await audio.play();\n"
        f"      console.log('[Speak] 재생 시작');\n"
        f"    }} catch (e) {{\n"
        f"      if (e && e.name === 'AbortError') return;\n"
        f"      console.warn('[Speak] ElevenLabs 실패, 폴백 실행:', e.message);\n"
        f"      const synth = __rmOwner.speechSynthesis || window.speechSynthesis;\n"
        f"      if (!synth) {{ finish(); return; }}\n"
        f"      const u = new SpeechSynthesisUtterance(t);\n"
        f"      u.lang = 'ko-KR';\n"
        f"      u.rate = __rmOwner.__rmVoiceSpeed || 1.0;\n"
        f"      u.onend = finish;\n"
        f"      u.onerror = finish;\n"
        f"      synth.speak(u);\n"
        f"    }}\n"
        f"  }}"
    )
