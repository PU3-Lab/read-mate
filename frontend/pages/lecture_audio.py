import streamlit as st
from components.result_panel import render_result_panel
from job_runner import (
    get_analysis_job_progress,
    get_analysis_job_result,
    submit_analysis_job,
)
from speak_js import get_announcement_token, make_speak_fn

from pipelines import analyze_content

_A11Y_TEMPLATE = """
<script>
(function(){
__SPEAK_FN__

  // 진입 안내 → 업로드 버튼 포커스
  function init(){
    speakOnce(
      `audio-intro:__INTRO_TOKEN__`,
      '강의 녹음 분석입니다. 탭 키를 눌러 파일 업로드 버튼으로 이동하세요. 파일을 선택하면 안내해드립니다.',
      ()=>{
        const btn=window.parent.document.querySelector('[data-testid="stFileUploaderDropzoneInput"]');
        if(btn) btn.focus();
      }
    );
  }
  setTimeout(init, 500);

  function attachFocus(){
    // 1. Buttons (탭 순서에서 제외)
    window.parent.document.querySelectorAll('button').forEach(b=>{
      if(b._rmAttached) return;
      b._rmAttached=true;
      b.setAttribute('tabindex', '-1');
      b.addEventListener('focus',()=>{
        const t=b.innerText.trim();
        if(t.includes('분석 시작')) speak('분석 시작 버튼입니다. 엔터를 눌러주세요.');
        else if(t.includes('ReadMate')) speak('홈화면으로 돌아가기 버튼입니다.');
      });
    });

    // 2. Summary Card
    window.parent.document.querySelectorAll('.rm-summary-card').forEach(c=>{
      if(c._rmAttached) return;
      c._rmAttached=true;
      if(!c.getAttribute('tabindex')) c.setAttribute('tabindex', '0');
      c.addEventListener('focus', ()=>{
        speak('분석 요약 결과입니다. 읽어드릴까요? 알키 를 누르면 다시 읽어드립니다.');
      });
    });
  }

  // Focus Trapping
  function handleTab(e) {
    if (e.key !== 'Tab') return;
    const doc = window.parent.document;
    const focusables = Array.from(doc.querySelectorAll('button, [tabindex="0"], input, textarea, select, a'))
      .filter(el => {
        if (el.getAttribute('tabindex') === '-1') return false;
        if (el.offsetWidth <= 0 && el.offsetHeight <= 0) return false;
        const style = window.parent.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden') return false;
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

  // 파일 선택 완료 감지
  let announced=false;
  const obs2=new MutationObserver(()=>{
    if(announced)return;
    const audio=window.parent.document.querySelector('audio');
    const fname=window.parent.document.querySelector('[data-testid="stFileUploaderFileName"]');
    if(!audio&&!fname)return;
    announced=true;
    const name=fname?fname.textContent.trim():'녹음 파일';
    speak(`${name} 파일이 선택되었습니다.`,()=>{
      speak('탭 키를 눌러 분석 시작 버튼으로 이동한 뒤 엔터를 눌러주세요.',()=>{
        const btns=window.parent.document.querySelectorAll('button');
        for(const b of btns){if(b.innerText.includes('분석 시작')){b.focus();break;}}
      });
    });
  });
  obs2.observe(window.parent.document.body,{childList:true,subtree:true,characterData:true});

  // Backspace → 뒤로
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


def _a11y_js() -> str:
    intro_token = get_announcement_token('audio:upload')
    return (
        _A11Y_TEMPLATE.replace('__SPEAK_FN__', make_speak_fn()).replace(
            '__INTRO_TOKEN__',
            str(intro_token),
        )
    )


def render() -> None:
    if st.session_state.get('processing_error'):
        st.error(st.session_state.processing_error)

    st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
    if st.button('ReadMate', key='back_audio'):
        _reset()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="rm-page-title">🎧 강의 녹음 분석</div>', unsafe_allow_html=True
    )

    if st.session_state.get('processing_job'):
        render_result_panel()
        _continue_processing()
    elif not st.session_state.get('raw_text'):
        st.markdown(
            """
        <div class="kb-hint">
          <strong>Tab</strong> : 버튼 이동 &nbsp;|&nbsp;
          <strong>Enter</strong> : 파일 탐색기 열기<br>
          파일 선택 후 → <strong>Tab</strong> 으로 분석 시작 버튼 →
          <strong>Enter</strong> &nbsp;|&nbsp;
          <strong>Backspace</strong> : 뒤로가기
        </div>
        """,
            unsafe_allow_html=True,
        )

        uploaded = st.file_uploader(
            '녹음 파일 (MP3 · WAV · M4A · OGG · FLAC)',
            type=['mp3', 'wav', 'm4a', 'ogg', 'flac'],
            label_visibility='visible',
        )

        if uploaded:
            ext = uploaded.name.split('.')[-1].lower()
            st.audio(uploaded, format=f'audio/{ext}')
            if st.button('분석 시작', width='stretch', key='run_audio'):
                _tts_notify('분석을 시작합니다. 잠시만 기다려 주세요')
                _queue_processing(uploaded.name, uploaded.getvalue())
                st.rerun()

        st.iframe(_a11y_js(), height=1)

    else:
        render_result_panel()


def _tts_notify(msg: str) -> None:
    """Python 단계 전환 시 백엔드 TTS로 안내 메시지를 재생한다."""
    speak_js_code = make_speak_fn()
    safe = msg.replace("'", "\\'")
    st.iframe(
        f"""
<script>
(function(){{
{speak_js_code}
  speak('{safe}');
}})();
</script>
""",
        height=1,
    )


def _run(file_name: str, audio_bytes: bytes) -> bool:
    """오디오 파일을 ReadingPipeline으로 분석한다."""
    try:
        with st.spinner('🎧 녹음 파일 분석 중...'):
            result = analyze_content(file_name=file_name, content=audio_bytes)
    except Exception as exc:
        st.error(f'분석 실패: {exc}')
        return False

    st.session_state.raw_text = result['raw_text']
    st.session_state.summary = result['summary']
    st.session_state.quiz = result['quiz']
    st.session_state.memo_keywords = result['memo_keywords']
    st.session_state.audio_bytes = result['audio_bytes']
    st.session_state.audio_mime = result.get('audio_mime')
    st.session_state.audio_file_name = result.get('audio_file_name')
    st.session_state.pipeline_warnings = result['pipeline_warnings']
    st.session_state.qa_history = []
    st.session_state.active_panel = 'summary'
    st.session_state.summary_play_key = ''
    st.session_state.summary_play_token = 0
    st.session_state.qa_new_answer = False
    st.session_state.qa_answer_play_token = 0
    return True


def _queue_processing(file_name: str, audio_bytes: bytes) -> None:
    """오디오 분석 작업을 세션 상태에 적재한다."""
    job_id = submit_analysis_job(
        file_name=file_name,
        content=audio_bytes,
        voice_preset=st.session_state.get('selected_voice', 'JiYeong Kang'),
    )
    st.session_state.processing_job = {
        'job_id': job_id,
        'input_label': '음성 인식',
    }
    st.session_state.processing_step = 'analysis'
    st.session_state.processing_message = (
        '분석중입니다. 음성 인식과 요약을 준비하고 있습니다.'
    )
    st.session_state.processing_error = ''
    st.session_state.raw_text = ''
    st.session_state.summary = ''
    st.session_state.quiz = []
    st.session_state.memo_keywords = []
    st.session_state.audio_bytes = None
    st.session_state.audio_mime = None
    st.session_state.audio_file_name = None
    st.session_state.pipeline_warnings = []
    st.session_state.qa_history = []
    st.session_state.active_panel = 'summary'
    st.session_state.summary_play_key = ''
    st.session_state.summary_play_token = 0
    st.session_state.qa_new_answer = False
    st.session_state.qa_answer_play_token = 0


_PROGRESS_TTS: dict[str, str] = {
    '음성': '잠시만 기다려 주세요',
    'LLM': '잠시만 기다려 주세요',
    'TTS': '잠시만 기다려 주세요',
}
_last_tts_msg: dict = {}

@st.fragment(run_every='1.0s')
def _render_processing_status(job_id: str):
    """진행 상황을 껌벅임 없이 업데이트하기 위한 프래그먼트."""
    try:
        result = get_analysis_job_result(job_id)
    except Exception as exc:
        st.session_state.processing_error = f'분석 실패: {exc}'
        st.session_state.processing_job = None
        st.session_state.processing_step = None
        st.session_state.processing_message = ''
        st.rerun()
        return

    if result is None:
        # 아직 진행 중: CSS 스피너와 함께 진행 메시지 표시
        current_msg = get_analysis_job_progress(job_id)

        tts_msg = next(
            (v for k, v in _PROGRESS_TTS.items() if k in current_msg),
            '잠시만 기다려 주세요',
        )
        step_changed = _last_tts_msg.get(job_id) != tts_msg
        if step_changed:
            _last_tts_msg[job_id] = tts_msg

        safe_msg = tts_msg.replace("'", "\\'")
        st.iframe(
            f"""
<script>
(function() {{
  {make_speak_fn()}

  if (window._rmTtsInterval) {{
    clearInterval(window._rmTtsInterval);
    window._rmTtsInterval = null;
  }}

  {'speak("' + safe_msg + '", null, {priority:"high"});' if step_changed else ''}

  window._rmTtsInterval = setInterval(() => speak('{safe_msg}', null, {{priority:'high'}}), 8000);
}})();
</script>
""",
            height=1,
        )

        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 12px; padding: 1rem; background: #f8f9fa; border-radius: 10px; border: 1px solid #e9ecef;">
                <div class="rm-loader"></div>
                <div style="color: #495057; font-weight: 500;">{current_msg}</div>
            </div>
            <style>
                .rm-loader {{
                    border: 3px solid #f3f3f3;
                    border-radius: 50%;
                    border-top: 3px solid #ff7e5f;
                    width: 24px;
                    height: 24px;
                    animation: rm-spin 1s linear infinite;
                }}
                @keyframes rm-spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
            </style>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.iframe(
            """
<script>
(function() {
  if (window._rmTtsInterval) {
    clearInterval(window._rmTtsInterval);
    window._rmTtsInterval = null;
  }
  if (window.speechSynthesis) window.speechSynthesis.cancel();
})();
</script>
""",
            height=1,
        )
        # 작업 완료: 결과를 세션 상태에 저장하고 전체 페이지 리런
        st.session_state.raw_text = result['raw_text']
        st.session_state.summary = result['summary']
        st.session_state.quiz = result['quiz']
        st.session_state.memo_keywords = result['memo_keywords']
        st.session_state.audio_bytes = result['audio_bytes']
        st.session_state.audio_mime = result.get('audio_mime')
        st.session_state.audio_file_name = result.get('audio_file_name')
        st.session_state.pipeline_warnings = result['pipeline_warnings']
        st.session_state.processing_job = None
        st.session_state.processing_step = None
        st.session_state.processing_message = ''
        st.session_state.summary_play_key = ''
        st.session_state.summary_play_token = 0
        st.session_state.qa_answer_play_token = 0
        st.rerun()


def _continue_processing() -> None:
    """세션에 적재된 오디오 분석 작업을 실행한다."""
    job = st.session_state.get('processing_job')
    if not job:
        return

    # 프래그먼트 호출 (부분 갱신 시작)
    _render_processing_status(job['job_id'])


def _reset():
    for k in [
        'raw_text',
        'summary',
        'quiz',
        'memo_keywords',
        'qa_history',
        'audio_bytes',
        'audio_mime',
        'audio_file_name',
        'active_panel',
        'qa_new_answer',
        'feature',
        'pipeline_warnings',
        'processing_error',
        'processing_job',
        'processing_step',
        'processing_message',
        'summary_play_key',
        'summary_play_token',
        'qa_answer_play_token',
    ]:
        st.session_state[k] = (
            None
            if k
            in (
                'audio_bytes',
                'audio_mime',
                'audio_file_name',
                'feature',
                'processing_job',
                'processing_step',
            )
            else []
            if k in ('quiz', 'memo_keywords', 'qa_history')
            else False
            if k == 'qa_new_answer'
            else []
            if k == 'pipeline_warnings'
            else ''
            if k == 'processing_error'
            else 'summary'
            if k == 'active_panel'
            else 0
            if k in ('summary_play_token', 'qa_answer_play_token')
            else ''
        )
