import streamlit as st
import sys, os, importlib.util, pathlib

st.set_page_config(
    page_title="Read Mate",
    page_icon="📖",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# frontend/ 루트를 sys.path 에 등록
_ROOT = os.path.abspath(os.path.dirname(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from styles import inject_styles
inject_styles()


def init():
    defaults = {
        "feature":       None,
        "raw_text":      "",
        "summary":       "",
        "quiz":          [],
        "memo_keywords": [],
        "qa_history":    [],
        "audio_bytes":   None,
        "pipeline_warnings": [],
        "active_panel":  "summary",
        "qa_new_answer": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init()


def load_page(name: str):
    path = pathlib.Path(__file__).parent / "pages" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 헤더 ─────────────────────────────────────
st.markdown("""
<div class="rm-header">
  <div class="rm-logo">
    <img src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIiB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCI+CiAgPCEtLSDssYUg7Jm87Kq9IO2OmOydtOyngCAtLT4KICA8cmVjdCB4PSI4IiB5PSIxNSIgd2lkdGg9IjM4IiBoZWlnaHQ9IjcwIiByeD0iNCIgcnk9IjQiIGZpbGw9IiNmZjdlNWYiLz4KICA8IS0tIOyxhSDsmKTrpbjsqr0g7Y6Y7J207KeAIC0tPgogIDxyZWN0IHg9IjU0IiB5PSIxNSIgd2lkdGg9IjM4IiBoZWlnaHQ9IjcwIiByeD0iNCIgcnk9IjQiIGZpbGw9IiNmOWEwM2YiLz4KICA8IS0tIOyxhSDsspnstpQo6rCA7Jq0642wIOyEoCkgLS0+CiAgPHJlY3QgeD0iNDQiIHk9IjE1IiB3aWR0aD0iMTIiIGhlaWdodD0iNzAiIHJ4PSIyIiByeT0iMiIgZmlsbD0iI2U4NmE0NSIvPgogIDwhLS0g7Jm87Kq9IO2OmOydtOyngCDspIQgLS0+CiAgPGxpbmUgeDE9IjE2IiB5MT0iMzIiIHgyPSI0MCIgeTI9IjMyIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgb3BhY2l0eT0iMC42Ii8+CiAgPGxpbmUgeDE9IjE2IiB5MT0iNDIiIHgyPSI0MCIgeTI9IjQyIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgb3BhY2l0eT0iMC42Ii8+CiAgPGxpbmUgeDE9IjE2IiB5MT0iNTIiIHgyPSI0MCIgeTI9IjUyIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgb3BhY2l0eT0iMC42Ii8+CiAgPGxpbmUgeDE9IjE2IiB5MT0iNjIiIHgyPSI0MCIgeTI9IjYyIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgb3BhY2l0eT0iMC40Ii8+CiAgPCEtLSDsmKTrpbjsqr0g7Y6Y7J207KeAIOykhCAtLT4KICA8bGluZSB4MT0iNjAiIHkxPSIzMiIgeDI9Ijg0IiB5Mj0iMzIiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBvcGFjaXR5PSIwLjYiLz4KICA8bGluZSB4MT0iNjAiIHkxPSI0MiIgeDI9Ijg0IiB5Mj0iNDIiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBvcGFjaXR5PSIwLjYiLz4KICA8bGluZSB4MT0iNjAiIHkxPSI1MiIgeDI9Ijg0IiB5Mj0iNTIiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBvcGFjaXR5PSIwLjYiLz4KICA8bGluZSB4MT0iNjAiIHkxPSI2MiIgeDI9Ijg0IiB5Mj0iNjIiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBvcGFjaXR5PSIwLjQiLz4KPC9zdmc+" style="width:2.4rem;height:2.4rem;object-fit:contain;" alt="Read Mate 로고">
    <span class="rm-logo-text">Read<span class="accent">Mate</span></span>
  </div>
  <p class="rm-tagline">"소리로 읽는 강의 자료, 당신의 배움이 멈추지 않도록"</p>
</div>
""", unsafe_allow_html=True)


# ── 기능 선택 ─────────────────────────────────
if st.session_state.feature is None:

    st.markdown("""
    <div style="text-align:center;font-family:'Nunito',sans-serif;
         font-size:.95rem;font-weight:800;color:var(--text-muted);margin-bottom:1.2rem;">
      함께 듣고 싶은 자료가 있나요?
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("""
        <div class="feature-card">
          <div class="feature-icon">🎧</div>
          <div class="feature-title">강의 녹음 분석</div>
          <div class="feature-desc">녹음 파일을 올리면<br>요약·퀴즈·질의응답을 제공해요</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("1번 · 녹음 분석 시작", key="btn_audio", use_container_width=True):
            st.session_state.feature = "audio"
            st.rerun()

    with c2:
        st.markdown("""
        <div class="feature-card">
          <div class="feature-icon">📄</div>
          <div class="feature-title">강의 자료 분석</div>
          <div class="feature-desc">PDF 또는 이미지를 올리면<br>요약·퀴즈·질의응답을 제공해요</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("2번 · 자료 분석 시작", key="btn_material", use_container_width=True):
            st.session_state.feature = "material"
            st.rerun()

    # 음성 안내 + 포커스 + 전역 키
    st.components.v1.html("""
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

  function speak(t,cb){
    if(!window.speechSynthesis){if(cb)cb();return;}
    window.speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(t);
    u.lang='ko-KR';u.rate=1.0;
    if(cb)u.onend=cb;
    window.speechSynthesis.speak(u);
  }

  // 버튼 포커스 → 즉시 TTS
  function attachFocus(){
    window.parent.document.querySelectorAll('button').forEach(b=>{
      if(b._rmA)return; b._rmA=true;
      b.addEventListener('focus',()=>{
        const t=b.innerText.trim();
        if(t.includes('1번')) speak('첫번째 버튼, 강의 녹음 분석입니다. Enter 를 누르면 시작합니다.');
        else if(t.includes('2번')) speak('두번째 버튼, 강의 자료 분석입니다. Enter 를 누르면 시작합니다.');
      });
    });
  }
  const obs=new MutationObserver(attachFocus);
  obs.observe(window.parent.document.body,{childList:true,subtree:true});
  setTimeout(attachFocus,800);

  function activate(){
    if(active)return; active=true;
    document.getElementById('wake').style.display='none';
    document.getElementById('hint').style.display='block';
    speak(
      '리드메이트입니다. 소리로 읽는 강의자료, 배움의 끝이 없도록 우리 함께 공부해요. Tab키를 눌러 버튼으로 이동하세요. 첫번째 버튼은 강의 녹음 분석, 두번째 버튼은 강의 자료 분석입니다. Enter 를 눌러 선택하세요.',
      ()=>{
        const btns=window.parent.document.querySelectorAll('button');
        for(const b of btns){if(b.innerText.includes('1번')){b.focus();break;}}
      }
    );
  }

  document.addEventListener('keydown', activate, {once:true});
  document.addEventListener('click',   activate, {once:true});
  try{
    window.parent.document.addEventListener('keydown', activate, {once:true});
    window.parent.document.addEventListener('click',   activate, {once:true});
  }catch(e){}

  // 돌아왔을 때 (이미 인터랙션 있음)
  setTimeout(()=>{
    if(active) speak('리드메이트입니다. Tab 키를 눌러 기능을 선택하세요.');
  },600);
})();
</script>
""", height=70)


# ── 기능 페이지 ───────────────────────────────
elif st.session_state.feature == "audio":
    load_page("lecture_audio").render()

elif st.session_state.feature == "material":
    load_page("lecture_material").render()


# # ── 푸터 ─────────────────────────────────────
# st.markdown("""
# <div class="rm-footer">
#   Powered by Whisper · PaddleOCR · Qwen2.5 · MeloTTS &nbsp;|&nbsp; Read Mate v1.0
# </div>
# """, unsafe_allow_html=True)
