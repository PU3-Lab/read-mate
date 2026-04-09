import os

import requests
import streamlit as st
from speak_js import get_announcement_token, get_server_url, make_speak_fn

_A11Y_TEMPLATE = """
<script>
(function(){
__SPEAK_FN__

  function init(){
    speakOnce(
      `voice-settings:__INTRO_TOKEN__`,
      '내 목소리 설정입니다. 화자 이름을 입력하고, 오디오 파일을 업로드한 뒤 등록 버튼을 눌러주세요.',
      ()=>{
        const inp=window.parent.document.querySelector('input[type="text"]');
        if(inp) inp.focus();
      }
    );
  }
  setTimeout(init, 500);

  function attachFocus(){
    window.parent.document.querySelectorAll('button').forEach(b=>{
      if(b._rmAttached) return;
      b._rmAttached=true;
      b.addEventListener('focus',()=>{
        const t=b.innerText.trim();
        if(t.includes('목소리 등록')) speak('목소리 등록 버튼입니다. 엔터를 눌러주세요.');
        else if(t.includes('ReadMate')) speak('홈화면으로 돌아가기 버튼입니다.');
      });
    });
  }

  // Focus Trapping
  function handleTab(e) {
    if (e.key !== 'Tab') return;
    const doc = window.parent.document;
    const focusables = Array.from(doc.querySelectorAll('button, [tabindex="0"], input, textarea, select, a'))
      .filter(el => {
        if (el.offsetWidth <= 0 && el.offsetHeight <= 0) return false;
        if (window.parent.getComputedStyle(el).display === 'none') return false;
        return true;
      });
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = doc.activeElement;
    if (e.shiftKey) {
      if (active === first || !focusables.includes(active)) { last.focus(); e.preventDefault(); }
    } else {
      if (active === last || !focusables.includes(active)) { first.focus(); e.preventDefault(); }
    }
  }
  if (!window.parent._rmTabHandler) {
    window.parent._rmTabHandler = handleTab;
    window.parent.document.addEventListener('keydown', window.parent._rmTabHandler);
  }

  const obs=new MutationObserver(attachFocus);
  obs.observe(window.parent.document.body,{childList:true,subtree:true});
  setTimeout(attachFocus,800);

  function onKey(e){
    const tag=e.target.tagName;
    if(tag==='INPUT'||tag==='TEXTAREA')return;
    if(e.key==='Backspace'){
      e.preventDefault();
      speak('기능 선택 화면으로 돌아갑니다.',()=>{
        const btns=window.parent.document.querySelectorAll('button');
        for(const b of btns){if(b.innerText.trim()==='ReadMate'){b.click();break;}}
      });
    }
  }
  document.addEventListener('keydown',onKey);
  try{window.parent.document.addEventListener('keydown',onKey);}catch(err){}
})();
</script>
"""

_SERVER_URL = os.getenv('LLM_SERVER_URL', get_server_url()).rstrip('/')

_PREVIEW_STYLE = """
<style>
.voice-preview-box {
  background: var(--surface2);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: .8rem 1rem;
  margin: .6rem 0 1rem;
  max-height: 260px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: .4rem;
}
.voice-preview-count {
  font-size: .88rem;
  font-weight: 700;
  color: var(--text-muted);
  margin-bottom: .2rem;
}
</style>
"""


def _load_voice_map() -> dict[str, str]:
    """백엔드에서 ElevenLabs 화자 목록(이름→ID)을 불러온다."""
    try:
        response = requests.get(f'{_SERVER_URL}/api/tts/voices', timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {}


def _a11y_js() -> str:
    intro_token = get_announcement_token('voice:settings')
    return (
        _A11Y_TEMPLATE.replace('__SPEAK_FN__', make_speak_fn()).replace(
            '__INTRO_TOKEN__',
            str(intro_token),
        )
    )


def render() -> None:
    """내 목소리 설정 페이지를 렌더링한다."""
    # ── 뒤로가기 버튼 ─────────────────────────
    st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
    if st.button('ReadMate', key='back_voice'):
        st.session_state.feature = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 페이지 제목 ───────────────────────────
    st.markdown(
        '<div class="rm-page-title">🎙 내 목소리 설정</div>', unsafe_allow_html=True
    )

    # ── 키보드 힌트 ───────────────────────────
    st.markdown(
        """
<div class="kb-hint">
  <strong>Tab</strong> : 항목 이동 &nbsp;|&nbsp;
  <strong>Enter</strong> : 파일 탐색기 열기<br>
  파일 선택 후 → <strong>Tab</strong> 으로 등록 버튼 →
  <strong>Enter</strong> &nbsp;|&nbsp;
  <strong>Backspace</strong> : 뒤로가기
</div>
""",
        unsafe_allow_html=True,
    )

    # ── 사용할 목소리 선택 ────────────────────
    st.markdown('#### 사용할 목소리 선택')
    voice_map = _load_voice_map()
    if voice_map:
        voice_names = list(voice_map.keys())
        current = st.session_state.get('selected_voice', 'JiYeong Kang')
        default_idx = voice_names.index(current) if current in voice_names else 0
        selected = st.selectbox(
            '목소리',
            options=voice_names,
            index=default_idx,
            label_visibility='collapsed',
        )
        if st.button('이 목소리로 설정', key='btn_set_voice', width='stretch'):
            st.session_state.selected_voice = selected
            st.success(f'**{selected}** 목소리로 설정되었습니다.')
    else:
        st.warning('ElevenLabs 화자 목록을 불러오지 못했습니다. API 키를 확인하세요.')

    st.divider()

    # ── 재생 속도 설정 ────────────────────────
    st.markdown('#### 재생 속도 설정')
    _speed_options = [round(i * 0.1, 1) for i in range(1, 21)]  # 0.1 ~ 2.0
    _current_speed = st.session_state.get('voice_speed', 1.0)
    _nearest = min(_speed_options, key=lambda x: abs(x - _current_speed))
    selected_speed = st.select_slider(
        '재생 속도',
        options=_speed_options,
        value=_nearest,
        format_func=lambda x: f'{x:.1f}',
        label_visibility='collapsed',
    )
    st.session_state.voice_speed = selected_speed
    st.caption('기본값 1.0 · 최소 0.1 · 최대 2.0')

    st.divider()

    # ── 새 목소리 클론 등록 ───────────────────
    st.markdown('#### 새 목소리 등록 (Voice Clone)')

    # ── 폼 ────────────────────────────────────
    voice_name = st.text_input(
        '화자 이름',
        placeholder='예: 홍길동',
        help='ElevenLabs에 등록될 화자 이름입니다.',
    )

    uploaded_files = st.file_uploader(
        'WAV 파일 (여러 개 선택 가능 · 각 10초 이상 권장)',
        type=['wav'],
        accept_multiple_files=True,
        label_visibility='visible',
    )

    # ── 오디오 미리듣기 (스크롤 박스) ─────────
    st.markdown(_PREVIEW_STYLE, unsafe_allow_html=True)
    if uploaded_files:
        st.markdown(
            f'<div class="voice-preview-count">{len(uploaded_files)}개 파일 선택됨</div>',
            unsafe_allow_html=True,
        )
        for f in uploaded_files:
            st.audio(f.getvalue(), format='audio/wav')

    # ── 등록 버튼 (항상 고정 위치) ────────────
    if st.button('목소리 등록', width='stretch', key='run_voice_clone'):
        if not voice_name.strip():
            st.error('화자 이름을 입력해주세요.')
        elif not uploaded_files:
            st.error('WAV 파일을 1개 이상 업로드해주세요.')
        else:
            _clone_voice(voice_name.strip(), uploaded_files)

    st.iframe(_a11y_js(), height=1)


def _clone_voice(name: str, uploaded_files: list) -> None:
    """업로드된 WAV 파일을 백엔드 TTS 라우트로 보내 보이스 클론을 생성한다."""
    with st.spinner('🎙 목소리를 등록하고 있습니다...'):
        try:
            files = [
                ('files', (uploaded.name, uploaded.getvalue(), 'audio/wav'))
                for uploaded in uploaded_files
            ]
            response = requests.post(
                f'{_SERVER_URL}/api/tts/clone-voice',
                data={'name': name},
                files=files,
                timeout=180,
            )
            response.raise_for_status()
            voice_id = response.json()['voice_id']
        except Exception as exc:
            st.error(f'등록 실패: {exc}')
            return

    st.session_state.selected_voice = name
    st.success(f'등록 완료! 화자 이름: **{name}** · Voice ID: `{voice_id}`')
    st.info('이제 분석 화면에서 이 화자를 선택해 음성을 들을 수 있습니다.')
