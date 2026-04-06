import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(sys.argv[0])))

import streamlit as st
from components.result_panel import render_result_panel
from services.mock_service   import mock_ocr, mock_llm, mock_tts


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
      '강의 자료 분석입니다. Tab 키를 눌러 파일 업로드 버튼으로 이동하세요. 파일을 선택하면 안내해드립니다.',
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
        for(const b of btns){if(b.innerText.includes('돌아가기')){b.click();break;}}
      });
    }
  }
  document.addEventListener('keydown',onKey);
  try{window.parent.document.addEventListener('keydown',onKey);}catch(err){}
})();
</script>
"""


def render():
    st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
    if st.button("ReadMate", key="back_material"):
        _reset(); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="rm-card">
      <div class="rm-card-title">📄 강의 자료 분석</div>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.get("raw_text"):

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
            "강의 자료 (PDF · JPG · PNG · WEBP)",
            type=["pdf","jpg","jpeg","png","webp","bmp"],
            label_visibility="visible",
        )

        if uploaded:
            upload_data = None
            if uploaded.name.lower().endswith(".pdf"):
                st.info(f"📄 {uploaded.name}")
                try:
                    import fitz
                    from PIL import Image as PILImage
                    fb = uploaded.read()
                    doc = fitz.open(stream=fb, filetype="pdf")
                    total = len(doc)
                    pidx = 0
                    if total > 1:
                        pidx = st.number_input(f"분석할 페이지 (1~{total})", 1, total, 1, 1) - 1
                    pix = doc[pidx].get_pixmap(matrix=fitz.Matrix(1.2,1.2))
                    img = PILImage.frombytes("RGB",[pix.width,pix.height],pix.samples)
                    st.image(img, caption=f"{pidx+1}/{total} 페이지", use_container_width=True)
                    upload_data = ("pdf", fb, pidx)
                except ImportError:
                    upload_data = ("pdf_raw", uploaded.read(), 0)
            else:
                from PIL import Image as PILImage
                img = PILImage.open(uploaded).convert("RGB")
                st.image(img, caption="업로드된 이미지", use_container_width=True)
                upload_data = ("image", img, 0)

            if upload_data and st.button("분석 시작", use_container_width=True, key="run_material"):
                _run(upload_data)
                st.rerun()

        st.components.v1.html(_A11Y_JS, height=0)

    else:
        render_result_panel()


def _run(upload_data):
    _, data, _ = upload_data
    with st.spinner("📄 텍스트 추출 중 (OCR)..."):
        text = mock_ocr(data)
    with st.spinner("🤖 AI 분석 중 (Qwen2.5)..."):
        result = mock_llm(text)

    st.session_state.raw_text      = text
    st.session_state.summary       = result["summary"]
    st.session_state.quiz          = result["quiz"]
    st.session_state.memo_keywords = result["memo_keywords"]
    st.session_state.qa_history    = []
    st.session_state.active_panel  = "summary"
    st.session_state.qa_new_answer = False

    with st.spinner("🔊 음성 합성 중..."):
        audio = mock_tts(result["summary"])
    st.session_state.audio_bytes = audio if audio else None


def _reset():
    for k in ["raw_text","summary","quiz","memo_keywords",
              "qa_history","audio_bytes","active_panel","qa_new_answer","feature"]:
        st.session_state[k] = (
            None  if k in ("audio_bytes","feature") else
            []    if k in ("quiz","memo_keywords","qa_history") else
            False if k == "qa_new_answer" else
            "summary" if k == "active_panel" else ""
        )
