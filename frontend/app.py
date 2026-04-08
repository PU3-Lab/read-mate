import importlib
import logging

import streamlit as st
from speak_js import make_speak_fn
from styles import inject_styles

from pipelines import get_default_reading_pipeline

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title='Read Mate',
    page_icon='📖',
    layout='centered',
    initial_sidebar_state='collapsed',
)

inject_styles()


def init():
    # 모델 미리 로드 (페이지 시작 시 한 번만 실행)
    if 'models_loaded' not in st.session_state:
        with st.spinner('시스템을 준비하고 있습니다... (모델 로딩 중)'):
            try:
                get_default_reading_pipeline()
                st.session_state.models_loaded = True
                logger.info('=========================================')
                logger.info(' Streamlit 사전로딩 완료: 시스템 준비됨! ')
                logger.info('=========================================')
            except Exception as e:
                logger.error(f'모델 로딩 실패: {e}')
                st.error(f'모델 로딩 실패: {e}')

    defaults = {
        'feature': None,
        'raw_text': '',
        'summary': '',
        'quiz': [],
        'memo_keywords': [],
        'qa_history': [],
        'audio_bytes': None,
        'audio_mime': None,
        'audio_file_name': None,
        'pipeline_warnings': [],
        'processing_error': '',
        'processing_job': None,
        'processing_step': None,
        'processing_message': '',
        'active_panel': 'summary',
        'summary_play_key': '',
        'summary_play_token': 0,
        'qa_new_answer': False,
        'selected_voice': 'JiYeong Kang',
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init()


def load_page(name: str):
    return importlib.import_module(f'pages.{name}')


_HOME_A11Y_TEMPLATE = """
<style>
#wake{
  background:#fff8f2;border:2px solid #ff7e5f;border-radius:16px;
  padding:1rem 1.4rem;text-align:center;
  font-family:'Gowun Dodum',sans-serif;font-size:.95rem;
  font-weight:800;color:#ff7e5f;margin-bottom:.5rem;
}
#hint{
  background:#fff8f2;border:1.5px dashed #f0cbb0;border-radius:16px;
  padding:.9rem 1.2rem;text-align:center;
  font-family:'Gowun Dodum',sans-serif;font-size:.82rem;
  font-weight:700;color:#b09a88;line-height:1.8;display:none;
}
</style>
<div id="wake">함께 듣고 싶은 자료가 있다면, 화면을 눌러 알려주세요</div>
<div id="hint">
  <strong style="color:#ff7e5f;">Tab</strong> : 버튼 이동 &nbsp;|&nbsp;
  <strong style="color:#ff7e5f;">Enter</strong> : 선택
</div>
<script>
(function(){
  let active=false;
__SPEAK_FN__

  function attachFocus(){
    // 1. Feature Cards
    window.parent.document.querySelectorAll('.feature-card').forEach(c=>{
      if(c._rmA)return; c._rmA=true;
      if(!c.getAttribute('tabindex')) c.setAttribute('tabindex', '0');
      
      c.addEventListener('focus',()=>{
        const title=c.querySelector('.feature-title').innerText.trim();
        if(title.includes('녹음')) speak('첫번째 버튼, 강의 녹음 분석입니다. 엔터를 누르면 시작합니다.');
        else if(title.includes('자료')) speak('두번째 버튼, 강의 자료 분석입니다. 엔터를 누르면 시작합니다.');
        else if(title.includes('목소리')) speak('세번째 버튼, 내 목소리 설정입니다. 엔터를 누르면 시작합니다.');
        else speak(title + ' 기능을 선택했습니다. 엔터를 누르면 시작합니다.');
      });
      c.addEventListener('click', ()=>{
        const btn = c.closest('[data-testid="stVerticalBlock"]').querySelector('button');
        if(btn) btn.click();
      });
      c.addEventListener('keydown', (e)=>{
        if(e.key==='Enter'){
          const btn = c.closest('[data-testid="stVerticalBlock"]').querySelector('button');
          if(btn) btn.click();
        }
      });
    });

    // 2. Buttons (탭 순서에서 제외하여 카드만 선택되게 함)
    window.parent.document.querySelectorAll('button').forEach(b=>{
      if(b._rmA)return; b._rmA=true;
      b.setAttribute('tabindex', '-1');
      b.addEventListener('focus',()=>{
        const t=b.innerText.trim();
        if(t.includes('1번')) speak('첫번째 버튼, 강의 녹음 분석입니다. 엔터를 누르면 시작합니다.');
        else if(t.includes('2번')) speak('두번째 버튼, 강의 자료 분석입니다. 엔터를 누르면 시작합니다.');
        else if(t.includes('3번')) speak('세번째 버튼, 내 목소리 설정입니다. 엔터를 누르면 시작합니다.');
        else speak(t + ' 버튼입니다.');
      });
    });
  }

  // Focus Trapping (Streamlit UI 안에서만 이동)
  function handleTab(e) {
    if (e.key !== 'Tab') return;
    const doc = window.parent.document;
    
    // 포커스 가능한 모든 요소 (Streamlit 내부)
    const focusables = Array.from(doc.querySelectorAll('button, [tabindex="0"], input, textarea, select, a, [contenteditable="true"]'))
      .filter(el => {
        // 보이지 않는 요소 제외 및 탭 순서 확인
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
      // Shift + Tab: 첫 번째 요소에서 마지막으로 이동
      if (active === first || !focusables.includes(active)) {
        last.focus();
        e.preventDefault();
      }
    } else {
      // Tab: 마지막 요소에서 첫 번째로 이동
      if (active === last || !focusables.includes(active)) {
        first.focus();
        e.preventDefault();
      }
    }
  }

  const obs=new MutationObserver(attachFocus);
  obs.observe(window.parent.document.body,{childList:true,subtree:true});
  setTimeout(attachFocus,800);

  function activate(){
    if(active)return; active=true;
    document.getElementById('wake').style.display='none';
    document.getElementById('hint').style.display='block';
    
    if (!window.parent._rmTabHandler) {
      window.parent._rmTabHandler = handleTab;
      window.parent.document.addEventListener('keydown', window.parent._rmTabHandler);
    }

    speak(
      '리드메이트입니다. 소리로 읽는 강의자료, 배움의 끝이 없도록 우리 함께 공부해요. 탭키를 눌러 버튼으로 이동하세요. 첫번째 버튼은 강의 녹음 분석, 두번째 버튼은 강의 자료 분석, 세번째 버튼은 내 목소리 설정입니다. 엔터 를 눌러 선택하세요.',
      ()=>{
        const cards=window.parent.document.querySelectorAll('.feature-card');
        if(cards.length > 0) cards[0].focus();
      }
    );
  }

  document.addEventListener('keydown', activate, {once:true});
  document.addEventListener('click',   activate, {once:true});
  try{
    window.parent.document.addEventListener('keydown', activate, {once:true});
    window.parent.document.addEventListener('click',   activate, {once:true});
  }catch(e){}

  setTimeout(()=>{
    if(active) speak('리드메이트입니다. 탭 키를 눌러 기능을 선택하세요.');
  },600);
})();
</script>
"""


def _home_a11y_js() -> str:
    return _HOME_A11Y_TEMPLATE.replace('__SPEAK_FN__', make_speak_fn())


# ── 헤더 ─────────────────────────────────────
st.markdown(
    """
<div class="rm-header">
  <div class="rm-logo">
    <img src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIiB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCI+CiAgPCEtLSDssYUg7Jm87Kq9IO2OmOydtOyngCAtLT4KICA8cmVjdCB4PSI4IiB5PSIxNSIgd2lkdGg9IjM4IiBoZWlnaHQ9IjcwIiByeD0iNCIgcnk9IjQiIGZpbGw9IiNmZjdlNWYiLz4KICA8IS0tIOyxhSDsmKTrpbjsqr0g7Y6Y7J207KeAIC0tPgogIDxyZWN0IHg9IjU0IiB5PSIxNSIgd2lkdGg9IjM4IiBoZWlnaHQ9IjcwIiByeD0iNCIgcnk9IjQiIGZpbGw9IiNmOWEwM2YiLz4KICA8IS0tIOyxhSDsspnstpQo6rCA7Jq0642wIOyEoCkgLS0+CiAgPHJlY3QgeD0iNDQiIHk9IjE1IiB3aWR0aD0iMTIiIGhlaWdodD0iNzAiIHJ4PSIyIiByeT0iMiIgZmlsbD0iI2U4NmE0NSIvPgogIDwhLS0g7Jm87Kq9IO2OmOydtOyngCDspIQgLS0+CiAgPGxpbmUgeDE9IjE2IiB5MT0iMzIiIHgyPSI0MCIgeTI9IjMyIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgb3BhY2l0eT0iMC42Ii8+CiAgPGxpbmUgeDE9IjE2IiB5MT0iNDIiIHgyPSI0MCIgeTI9IjQyIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgb3BhY2l0eT0iMC42Ii8+CiAgPGxpbmUgeDE9IjE2IiB5MT0iNTIiIHgyPSI0MCIgeTI9IjUyIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgb3BhY2l0eT0iMC42Ii8+CiAgPGxpbmUgeDE9IjE2IiB5MT0iNjIiIHgyPSI0MCIgeTI9IjYyIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgb3BhY2l0eT0iMC40Ii8+CiAgPCEtLSDsmKTrpbjsqr0g7Y6Y7J207KeAIOykhCAtLT4KICA8bGluZSB4MT0iNjAiIHkxPSIzMiIgeDI9Ijg0IiB5Mj0iMzIiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBvcGFjaXR5PSIwLjYiLz4KICA8bGluZSB4MT0iNjAiIHkxPSI0MiIgeDI9Ijg0IiB5Mj0iNDIiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBvcGFjaXR5PSIwLjYiLz4KICA8bGluZSB4MT0iNjAiIHkxPSI1MiIgeDI9Ijg0IiB5Mj0iNTIiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBvcGFjaXR5PSIwLjYiLz4KICA8bGluZSB4MT0iNjAiIHkxPSI2MiIgeDI9Ijg0IiB5Mj0iNjIiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBvcGFjaXR5PSIwLjQiLz4KPC9zdmc+" style="width:2.4rem;height:2.4rem;object-fit:contain;" alt="Read Mate 로고">
    <span class="rm-logo-text">Read<span class="accent">Mate</span></span>
  </div>
  <p class="rm-tagline">"소리로 읽는 강의 자료, 당신의 배움이 멈추지 않도록"</p>
</div>
""",
    unsafe_allow_html=True,
)


# ── 기능 선택 ─────────────────────────────────
if st.session_state.feature is None:
    st.markdown(
        """
    <div style="text-align:center;font-family:'Nunito',sans-serif;
         font-size:.95rem;font-weight:800;color:var(--text-muted);margin-bottom:1.2rem;">
      함께 듣고 싶은 자료가 있나요?
    </div>
    """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3, gap='large')
    with c1:
        st.markdown(
            """
<div class="feature-card" tabindex="0">
  <div class="feature-icon">🎧</div>
  <div class="feature-title">강의 녹음 분석</div>
  <div class="feature-desc">녹음 파일을 올리면<br>요약·퀴즈·질의응답을 제공해요</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button('1번 · 녹음 분석 시작', key='btn_audio', width='stretch'):
            st.session_state.feature = 'audio'
            st.rerun()

    with c2:
        st.markdown(
            """
<div class="feature-card" tabindex="0">
  <div class="feature-icon">📄</div>
  <div class="feature-title">강의 자료 분석</div>
  <div class="feature-desc">PDF 또는 이미지를 올리면<br>요약·퀴즈·질의응답을 제공해요</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button('2번 · 자료 분석 시작', key='btn_material', width='stretch'):
            st.session_state.feature = 'material'
            st.rerun()

    with c3:
        st.markdown(
            """
<div class="feature-card" tabindex="0">
  <div class="feature-icon">🎙</div>
  <div class="feature-title">내 목소리 설정</div>
  <div class="feature-desc">WAV 파일을 올리면<br>내 목소리로 읽어드려요</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button('3번 · 목소리 설정', key='btn_voice', width='stretch'):
            st.session_state.feature = 'voice'
            st.rerun()

    # 음성 안내 + 포커스 + 전역 키
    st.iframe(
        _home_a11y_js(),
        height=70,
    )


# ── 기능 페이지 ───────────────────────────────
elif st.session_state.feature == 'audio':
    load_page('lecture_audio').render()

elif st.session_state.feature == 'material':
    load_page('lecture_material').render()

elif st.session_state.feature == 'voice':
    load_page('voice_settings').render()


# # ── 푸터 ─────────────────────────────────────
# st.markdown("""
# <div class="rm-footer">
#   Powered by Whisper · PaddleOCR · Qwen2.5 · MeloTTS &nbsp;|&nbsp; Read Mate v1.0
# </div>
# """, unsafe_allow_html=True)
