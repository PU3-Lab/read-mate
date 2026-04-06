import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(sys.argv[0])))

import streamlit as st
from components.result_panel import render_result_panel
from job_runner import submit_analysis_job, wait_for_analysis_job
from pipelines import analyze_content


_A11Y_JS = """
<script>
(function(){
  function speak(t,cb){
    if(!window.speechSynthesis){if(cb)cb();return;}
    window.speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(t);
    u.lang='ko-KR';u.rate=1.0;
    if(cb)u.onend=cb;
    window.speechSynthesis.speak(u);
  }

  // 진입 안내 → 업로드 버튼 포커스
  function init(){
    speak(
      '강의 녹음 분석입니다. Tab 키를 눌러 파일 업로드 버튼으로 이동하세요. 파일을 선택하면 안내해드립니다.',
      ()=>{
        const btn=window.parent.document.querySelector('[data-testid="stFileUploaderDropzoneInput"]');
        if(btn) btn.focus();
      }
    );
  }
  setTimeout(init, 500);

  // 버튼 포커스 → 즉시 TTS
  function attachFocus(){
    window.parent.document.querySelectorAll('button').forEach(b=>{
      if(b._rmAttached) return;
      b._rmAttached=true;
      b.addEventListener('focus',()=>{
        const t=b.innerText.trim();
        if(t.includes('분석 시작')) speak('분석 시작 버튼입니다. Enter 를 눌러주세요.');
        else if(t.includes('돌아가기')) speak('홈화면으로 돌아가기 버튼입니다.');
      });
    });
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
      speak('Tab 키를 눌러 분석 시작 버튼으로 이동한 뒤 Enter 를 눌러주세요.',()=>{
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


def render() -> None:
    st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
    if st.button("ReadMate", key="back_audio"):
        _reset(); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="rm-page-title">🎧 강의 녹음 분석</div>', unsafe_allow_html=True)

    if st.session_state.get("processing_job"):
        render_result_panel()
        _continue_processing()
    elif not st.session_state.get("raw_text"):

        st.markdown("""
        <div class="kb-hint">
          <strong>Tab</strong> : 버튼 이동 &nbsp;|&nbsp;
          <strong>Enter</strong> : 파일 탐색기 열기<br>
          파일 선택 후 → <strong>Tab</strong> 으로 분석 시작 버튼 →
          <strong>Enter</strong> &nbsp;|&nbsp;
          <strong>Backspace</strong> : 뒤로가기
        </div>
        """, unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "녹음 파일 (MP3 · WAV · M4A · OGG · FLAC)",
            type=["mp3","wav","m4a","ogg","flac"],
            label_visibility="visible",
        )

        if uploaded:
            ext = uploaded.name.split(".")[-1].lower()
            st.audio(uploaded, format=f"audio/{ext}")
            if st.button("분석 시작", use_container_width=True, key="run_audio"):
                _queue_processing(uploaded.name, uploaded.getvalue())
                st.rerun()

        st.components.v1.html(_A11Y_JS, height=0)

    else:
        render_result_panel()


def _run(file_name: str, audio_bytes: bytes) -> bool:
    """오디오 파일을 ReadingPipeline으로 분석한다."""
    try:
        with st.spinner("🎧 녹음 파일 분석 중..."):
            result = analyze_content(file_name=file_name, content=audio_bytes)
    except Exception as exc:
        st.error(f'분석 실패: {exc}')
        return False

    st.session_state.raw_text = result['raw_text']
    st.session_state.summary = result['summary']
    st.session_state.quiz = result['quiz']
    st.session_state.memo_keywords = result['memo_keywords']
    st.session_state.audio_bytes = result['audio_bytes']
    st.session_state.pipeline_warnings = result['pipeline_warnings']
    st.session_state.qa_history = []
    st.session_state.active_panel = 'summary'
    st.session_state.qa_new_answer = False
    return True


def _queue_processing(file_name: str, audio_bytes: bytes) -> None:
    """오디오 분석 작업을 세션 상태에 적재한다."""
    job_id = submit_analysis_job(
        file_name=file_name,
        content=audio_bytes,
        voice_preset='default',
    )
    st.session_state.processing_job = {
        'job_id': job_id,
        'input_label': '음성 인식',
    }
    st.session_state.processing_step = 'analysis'
    st.session_state.processing_message = '분석중입니다. 음성 인식과 요약을 준비하고 있습니다.'
    st.session_state.raw_text = ''
    st.session_state.summary = ''
    st.session_state.quiz = []
    st.session_state.memo_keywords = []
    st.session_state.audio_bytes = None
    st.session_state.pipeline_warnings = []
    st.session_state.qa_history = []
    st.session_state.active_panel = 'summary'
    st.session_state.qa_new_answer = False


def _continue_processing() -> None:
    """세션에 적재된 오디오 분석 작업을 실행한다."""
    job = st.session_state.get('processing_job')
    if not job:
        return

    try:
        with st.spinner(st.session_state.get('processing_message', '분석중입니다...')):
            result = wait_for_analysis_job(job['job_id'])
    except Exception as exc:
        st.session_state.processing_job = None
        st.session_state.processing_step = None
        st.session_state.processing_message = ''
        st.error(f'분석 실패: {exc}')
        return

    st.session_state.raw_text = result['raw_text']
    st.session_state.summary = result['summary']
    st.session_state.quiz = result['quiz']
    st.session_state.memo_keywords = result['memo_keywords']
    st.session_state.audio_bytes = result['audio_bytes']
    st.session_state.pipeline_warnings = result['pipeline_warnings']
    st.session_state.processing_job = None
    st.session_state.processing_step = None
    st.session_state.processing_message = ''
    st.rerun()


def _reset():
    for k in ["raw_text","summary","quiz","memo_keywords",
              "qa_history","audio_bytes","active_panel","qa_new_answer",
              "feature","pipeline_warnings","processing_job",
              "processing_step","processing_message"]:
        st.session_state[k] = (
            None  if k in ("audio_bytes","feature","processing_job","processing_step") else
            []    if k in ("quiz","memo_keywords","qa_history") else
            False if k == "qa_new_answer" else
            []    if k == "pipeline_warnings" else
            "summary" if k == "active_panel" else ""
        )
