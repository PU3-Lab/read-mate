import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(sys.argv[0])))

import streamlit as st
import streamlit.components.v1 as components
from components.result_panel import render_result_panel
from services.mock_service   import mock_ocr, mock_llm, mock_tts


_INTRO_JS = """
<script>
(function(){
  function speak(t, cb){
    if(!window.speechSynthesis){if(cb)cb();return;}
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(t);
    u.lang='ko-KR'; u.rate=1.0;
    if(cb) u.onend=cb;
    window.speechSynthesis.speak(u);
  }

  setTimeout(()=>{
    speak(
      '강의 자료 분석입니다. ' +
      '1번, 파일 업로드. ' +
      '2번, 카메라 촬영. ' +
      '숫자키 1 또는 2를 눌러 선택하세요. ' +
      'Backspace 를 누르면 홈으로 돌아갑니다.'
    );
  }, 500);

  function attachFocus(){
    window.parent.document.querySelectorAll('button').forEach(b=>{
      if(b._rmA) return; b._rmA=true;
      b.addEventListener('focus', ()=>{
        const t = b.innerText.trim();
        if(t.includes('파일 업로드'))   speak('1번, 파일 업로드 버튼입니다. Enter 를 눌러주세요.');
        if(t.includes('카메라 촬영'))   speak('2번, 카메라 촬영 버튼입니다. Enter 를 눌러주세요.');
        if(t.includes('분석 시작'))     speak('분석 시작 버튼입니다. Enter 를 눌러주세요.');
      });
    });
  }
  const obs = new MutationObserver(attachFocus);
  obs.observe(window.parent.document.body, {childList:true, subtree:true});
  setTimeout(attachFocus, 800);

  function onKey(e){
    const tag = e.target.tagName;
    if(tag==='INPUT'||tag==='TEXTAREA') return;
    if(e.key==='1'){
      speak('파일 업로드를 선택했습니다.', ()=>{
        const btns = window.parent.document.querySelectorAll('button');
        for(const b of btns){ if(b.innerText.includes('파일 업로드')){ b.click(); break; } }
      });
    }
    if(e.key==='2'){
      speak('카메라 촬영을 선택했습니다.', ()=>{
        const btns = window.parent.document.querySelectorAll('button');
        for(const b of btns){ if(b.innerText.includes('카메라 촬영')){ b.click(); break; } }
      });
    }
    if(e.key==='Backspace'){
      e.preventDefault();
      speak('홈으로 돌아갑니다.', ()=>{
        const btns = window.parent.document.querySelectorAll('button');
        for(const b of btns){ if(b.innerText.trim()==='ReadMate'){ b.click(); break; } }
      });
    }
  }
  document.addEventListener('keydown', onKey);
  try{ window.parent.document.addEventListener('keydown', onKey); }catch(e){}
})();
</script>
"""

_UPLOAD_JS = """
<script>
(function(){
  function speak(t, cb){
    if(!window.speechSynthesis){if(cb)cb();return;}
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(t);
    u.lang='ko-KR'; u.rate=1.0;
    if(cb) u.onend=cb;
    window.speechSynthesis.speak(u);
  }

  setTimeout(()=>{
    speak(
      '파일 업로드 모드입니다. ' +
      'Tab 키를 눌러 파일 선택 버튼으로 이동하세요. ' +
      'Backspace 를 누르면 모드 선택으로 돌아갑니다.'
    );
  }, 400);

  let announced = false;
  const obs = new MutationObserver(()=>{
    if(announced) return;
    const fname = window.parent.document.querySelector('[data-testid="stFileUploaderFileName"]');
    if(!fname) return;
    announced = true;
    const name = fname.textContent.trim();
    speak(`${name} 파일이 선택되었습니다. Tab 키를 눌러 분석 시작 버튼으로 이동한 뒤 Enter 를 눌러주세요.`, ()=>{
      const btns = window.parent.document.querySelectorAll('button');
      for(const b of btns){ if(b.innerText.includes('분석 시작')){ b.focus(); break; } }
    });
  });
  obs.observe(window.parent.document.body, {childList:true, subtree:true, characterData:true});

  function attachFocus(){
    window.parent.document.querySelectorAll('button').forEach(b=>{
      if(b._rmA) return; b._rmA=true;
      b.addEventListener('focus', ()=>{
        const t = b.innerText.trim();
        if(t.includes('분석 시작')) speak('분석 시작 버튼입니다. Enter 를 눌러주세요.');
        if(t.includes('모드 선택')) speak('모드 선택으로 돌아가기 버튼입니다.');
      });
    });
  }
  const obs2 = new MutationObserver(attachFocus);
  obs2.observe(window.parent.document.body, {childList:true, subtree:true});
  setTimeout(attachFocus, 800);

  function onKey(e){
    const tag = e.target.tagName;
    if(tag==='INPUT'||tag==='TEXTAREA') return;
    if(e.key==='Backspace'){
      e.preventDefault();
      speak('모드 선택으로 돌아갑니다.', ()=>{
        const btns = window.parent.document.querySelectorAll('button');
        for(const b of btns){ if(b.innerText.includes('모드 선택')){ b.click(); break; } }
      });
    }
  }
  document.addEventListener('keydown', onKey);
  try{ window.parent.document.addEventListener('keydown', onKey); }catch(e){}
})();
</script>
"""

_CAMERA_HTML = """
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:transparent;font-family:'Gowun Dodum',sans-serif;}
#wrap{
  background:#edddd0;border:2px solid #7a5540;
  border-radius:20px;padding:1.4rem 1.4rem 1.8rem;text-align:center;
}
#status{
  font-size:1rem;font-weight:800;color:#1a0f0a;
  margin-bottom:.8rem;line-height:1.6;min-height:2.4rem;
}
video{
  width:100%;border-radius:14px;display:block;
  border:2px solid #7a5540;background:#1a0f0a;
  margin-bottom:.8rem;
}
canvas{display:none;}
#preview{
  width:100%;border-radius:14px;display:none;
  border:2px solid #8c2e10;margin-bottom:.8rem;
}
.btn-row{display:flex;gap:.6rem;flex-wrap:wrap;}
.cbtn{
  flex:1;border:none;border-radius:50px;
  padding:.75rem 0;font-size:1rem;font-weight:800;
  cursor:pointer;min-width:80px;
}
.cbtn.pri{background:#8c2e10;color:#fff;box-shadow:0 3px 10px rgba(140,46,16,.35);}
.cbtn.sec{background:#fff;color:#3d2010;border:2px solid #7a5540;}
.cbtn:disabled{background:#c8b0a0;color:#7a5540;cursor:default;box-shadow:none;}
#hint{font-size:.92rem;color:#3d2010;font-weight:700;margin-top:.8rem;line-height:1.9;}
</style>

<div id="wrap">
  <div id="status">⏳ 카메라를 불러오는 중입니다...</div>
  <video id="vid" autoplay playsinline></video>
  <canvas id="cvs"></canvas>
  <img id="preview" alt="촬영된 이미지">
  <div class="btn-row">
    <button class="cbtn pri" id="snap">📸 촬영 (Space)</button>
    <button class="cbtn sec" id="retry" style="display:none">다시 촬영 (R)</button>
    <button class="cbtn pri" id="use"   style="display:none">분석 시작 (Enter)</button>
  </div>
  <div id="hint">
    <strong>Space</strong> : 촬영 &nbsp;|&nbsp;
    <strong>Enter</strong> : 분석 시작 &nbsp;|&nbsp;
    <strong>R</strong> : 다시 촬영 &nbsp;|&nbsp;
    <strong>Backspace</strong> : 모드 선택으로
  </div>
</div>

<script>
(function(){
  const vid    = document.getElementById('vid');
  const cvs    = document.getElementById('cvs');
  const pre    = document.getElementById('preview');
  const snap   = document.getElementById('snap');
  const retry  = document.getElementById('retry');
  const use    = document.getElementById('use');
  const status = document.getElementById('status');

  let captured = false;

  function speak(t, cb){
    window.speechSynthesis && window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(t);
    u.lang='ko-KR'; u.rate=1.0;
    if(cb) u.onend=cb;
    window.speechSynthesis && window.speechSynthesis.speak(u);
  }

  speak('카메라를 불러오는 중입니다. 잠시 기다려주세요.', async ()=>{
    try{
      const stream = await navigator.mediaDevices.getUserMedia({
        video:{ facingMode:'user', width:{ideal:1280}, height:{ideal:720} }
      });
      vid.srcObject = stream;
      status.textContent = '📷 문서를 화면에 맞춰주세요';
      speak('카메라가 준비되었습니다. 문서를 화면 가득 채운 뒤 Space 를 눌러 촬영하세요.');
    }catch(err){
      status.textContent = '⚠️ 카메라 접근이 거부되었습니다.';
      speak('카메라 접근이 거부되었습니다. 브라우저에서 카메라 권한을 허용한 뒤 다시 시도해주세요.');
    }
  });

  function doSnap(){
    if(captured) return;
    cvs.width  = vid.videoWidth  || 640;
    cvs.height = vid.videoHeight || 480;
    cvs.getContext('2d').drawImage(vid, 0, 0);
    const dataUrl = cvs.toDataURL('image/jpeg', 0.92);
    pre.src = dataUrl;
    pre.style.display = 'block';
    vid.style.display = 'none';
    snap.style.display  = 'none';
    retry.style.display = '';
    use.style.display   = '';
    captured = true;
    status.textContent = '촬영 완료! 이미지를 확인하세요.';
    speak('촬영되었습니다. Enter 를 누르면 분석을 시작합니다. R 을 누르면 다시 촬영합니다.');
    window.parent.postMessage({type:'rm_camera', dataUrl:dataUrl}, '*');
  }

  function doRetry(){
    pre.style.display   = 'none';
    vid.style.display   = 'block';
    snap.style.display  = '';
    retry.style.display = 'none';
    use.style.display   = 'none';
    captured = false;
    status.textContent = '📷 문서를 화면에 맞춰주세요';
    speak('다시 촬영합니다. 문서를 화면에 맞추고 Space 를 눌러 촬영하세요.');
    window.parent.postMessage({type:'rm_camera', dataUrl:null}, '*');
  }

  function doUse(){
    speak('분석을 시작합니다. 잠시 기다려주세요.');
    window.parent.postMessage({type:'rm_camera_confirm'}, '*');
  }

  snap.onclick  = doSnap;
  retry.onclick = doRetry;
  use.onclick   = doUse;

  function onKey(e){
    const tag = e.target.tagName;
    if(tag==='INPUT'||tag==='TEXTAREA') return;
    if(e.code==='Space')          { e.preventDefault(); if(!captured) doSnap(); }
    if(e.code==='Enter')          { e.preventDefault(); if(captured)  doUse();  }
    if(e.key.toLowerCase()==='r') { if(captured) doRetry(); }
    if(e.key==='Backspace'){
      e.preventDefault();
      speak('모드 선택으로 돌아갑니다.',()=>window.parent.postMessage({type:'rm_go_mode'},'*'));
    }
  }
  document.addEventListener('keydown', onKey);
  try{ window.parent.document.addEventListener('keydown', onKey); }catch(e){}
})();
</script>
"""

# ── postMessage 수신 브릿지 (공통) ────────────────────
# rm_camera  → 카메라 이미지 데이터 저장
# rm_camera_confirm → 분석 시작 버튼 클릭
# rm_cam_back → 다시 촬영 후 모드 선택으로
# rm_cam_use  → 분석 시작 버튼 클릭
# rm_cam_retry→ 다시 촬영 버튼 클릭
_BRIDGE_JS = """
<script>
window.addEventListener('message', function(e){
  if(!e.data) return;
  const btns = window.parent.document.querySelectorAll('button');
  
  if(e.data.type==='rm_camera' && e.data.dataUrl){
    const inp = window.parent.document.querySelector('input[data-rmcam]');
    if(inp){ inp.value=e.data.dataUrl; inp.dispatchEvent(new Event('input',{bubbles:true})); }
  }
  
  if(e.data.type==='rm_camera_confirm'){
    for(const b of btns){ if(b.innerText.includes('분석 시작')){ b.click(); break; } }
  }
  
  if(e.data.type==='rm_cam_back'){
    for(const b of btns){ if(b.innerText.includes('모드 선택')){ b.click(); break; } }
  }
  
  if(e.data.type==='rm_cam_use'){
    for(const b of btns){ if(b.innerText.includes('분석 시작')){ b.click(); break; } }
  }
  
  if(e.data.type==='rm_cam_retry'){
    for(const b of btns){ if(b.innerText.includes('다시 촬영')){ b.click(); break; } }
  }
});
</script>
"""


def render():
    for k, v in [("input_mode", None), ("camera_image", None)]:
        if k not in st.session_state:
            st.session_state[k] = v

    st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
    if st.button("ReadMate", key="back_material"):
        _reset(); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="rm-page-title">📄 강의 자료 분석</div>', unsafe_allow_html=True)

    # 공통 브릿지 (항상 렌더)
    components.html(_BRIDGE_JS, height=0)

    if st.session_state.get("raw_text"):
        render_result_panel()

    else:

        # ── 모드 선택 ─────────────────────────────
        if st.session_state.input_mode is None:

            st.markdown("""
            <div class="kb-hint">
              <strong>1</strong> : 파일 업로드 &nbsp;|&nbsp;
              <strong>2</strong> : 카메라 촬영 &nbsp;|&nbsp;
              <strong>Backspace</strong> : 홈으로
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("""
                <div class="feature-card">
                  <div class="feature-icon">📁</div>
                  <div class="feature-title">파일 업로드</div>
                  <div class="feature-desc">PDF 또는 이미지 파일을<br>직접 올려 분석해요</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("1번 · 파일 업로드", key="mode_upload", use_container_width=True):
                    st.session_state.input_mode = "upload"
                    st.rerun()

            with c2:
                st.markdown("""
                <div class="feature-card">
                  <div class="feature-icon">📷</div>
                  <div class="feature-title">카메라 촬영</div>
                  <div class="feature-desc">카메라로 문서를 촬영하면<br>바로 분석해드려요</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("2번 · 카메라 촬영", key="mode_camera", use_container_width=True):
                    st.session_state.input_mode = "camera"
                    st.rerun()

            components.html(_INTRO_JS, height=0)

        # ── 파일 업로드 모드 ──────────────────────
        elif st.session_state.input_mode == "upload":

            st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
            if st.button("← 모드 선택", key="back_to_mode_upload"):
                st.session_state.input_mode = None; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("""
            <div class="kb-hint">
              <strong>Tab</strong> : 버튼 이동 &nbsp;|&nbsp;
              <strong>Enter</strong> : 파일 탐색기 열기<br>
              파일 선택 후 → <strong>Tab</strong> 으로 분석 시작 →
              <strong>Enter</strong> &nbsp;|&nbsp;
              <strong>Backspace</strong> : 모드 선택으로
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
                        pix = doc[pidx].get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
                        img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        st.image(img, caption=f"{pidx+1}/{total} 페이지", use_container_width=True)
                        upload_data = ("pdf", fb, pidx)
                    except ImportError:
                        upload_data = ("pdf_raw", uploaded.read(), 0)
                else:
                    from PIL import Image as PILImage
                    img = PILImage.open(uploaded).convert("RGB")
                    st.image(img, caption="업로드된 이미지", use_container_width=True)
                    upload_data = ("image", img, 0)

                if upload_data and st.button("분석 시작", use_container_width=True, key="run_upload"):
                    _run(upload_data)
                    st.rerun()

            components.html(_UPLOAD_JS, height=0)

        # ── 카메라 촬영 모드 ──────────────────────
        elif st.session_state.input_mode == "camera":

            st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
            if st.button("← 모드 선택", key="back_to_mode_camera"):
                st.session_state.input_mode = None
                st.session_state.camera_image = None
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

            if st.session_state.camera_image:
                from PIL import Image as PILImage
                import io, base64

                st.markdown("""
                <div class="kb-hint">
                  <strong>Enter</strong> : 분석 시작 &nbsp;|&nbsp;
                  <strong>R</strong> : 다시 촬영 &nbsp;|&nbsp;
                  <strong>Backspace</strong> : 모드 선택으로
                </div>
                """, unsafe_allow_html=True)

                img_data = st.session_state.camera_image
                _, b64 = img_data.split(",", 1)
                img = PILImage.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
                st.image(img, caption="촬영된 문서", use_container_width=True)

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("다시 촬영 (R)", use_container_width=True, key="cam_retry"):
                        st.session_state.camera_image = None
                        st.rerun()
                with c2:
                    if st.button("분석 시작 (Enter)", use_container_width=True, key="cam_use"):
                        _run(("image", img, 0))
                        st.session_state.camera_image = None
                        st.rerun()

                # 키 이벤트 → postMessage
                components.html("""
<script>
(function(){
  function speak(t,cb){
    window.speechSynthesis&&window.speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(t);
    u.lang='ko-KR';u.rate=1.0;if(cb)u.onend=cb;
    window.speechSynthesis&&window.speechSynthesis.speak(u);
  }
  setTimeout(()=>speak('촬영된 이미지입니다. Enter 로 분석을 시작하거나 R 로 다시 촬영하세요.'),400);
  function onKey(e){
    const tag=e.target.tagName;
    if(tag==='INPUT'||tag==='TEXTAREA')return;
    if(e.code==='Enter'){e.preventDefault();speak('분석을 시작합니다.',()=>window.parent.postMessage({type:'rm_cam_use'},'*'));}
    if(e.key.toLowerCase()==='r'){speak('다시 촬영합니다.',()=>window.parent.postMessage({type:'rm_cam_retry'},'*'));}
    if(e.key==='Backspace'){e.preventDefault();speak('모드 선택으로 돌아갑니다.',()=>window.parent.postMessage({type:'rm_cam_back'},'*'));}
  }
  document.addEventListener('keydown',onKey);
  try{window.parent.document.addEventListener('keydown',onKey);}catch(err){}
})();
</script>
""", height=0)

            else:
                components.html(_CAMERA_HTML, height=680, scrolling=False)

                cam_val = st.text_input("cam_bridge", key="cam_bridge", label_visibility="collapsed")
                components.html("""
<script>
(function(){
  const inputs=window.parent.document.querySelectorAll('input[type="text"]');
  inputs.forEach(inp=>{
    if(!inp.getAttribute('data-rmcam')){
      inp.setAttribute('data-rmcam','1');
      inp.style.position='absolute';
      inp.style.opacity='0';
      inp.style.pointerEvents='none';
      inp.style.height='0';
    }
  });
})();
</script>
""", height=0)

                if cam_val and cam_val.startswith("data:image"):
                    st.session_state.camera_image = cam_val
                    st.rerun()


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
              "qa_history","audio_bytes","active_panel","qa_new_answer",
              "feature","input_mode","camera_image"]:
        st.session_state[k] = (
            None  if k in ("audio_bytes","feature","input_mode","camera_image") else
            []    if k in ("quiz","memo_keywords","qa_history") else
            False if k == "qa_new_answer" else
            "summary" if k == "active_panel" else ""
        )