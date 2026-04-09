import base64
import io

import fitz
import streamlit as st
from components.result_panel import render_result_panel
from job_runner import (
    get_analysis_job_progress,
    get_analysis_job_result,
    submit_analysis_job,
)
from PIL import Image as PILImage
from speak_js import get_announcement_token, make_speak_fn

from pipelines import analyze_content

_INTRO_TEMPLATE = """
<script>
(function(){
__SPEAK_FN__

  function disableOwnFrame(){
    try{
      if(!window.frameElement) return;
      window.frameElement.setAttribute('tabindex', '-1');
      window.frameElement.setAttribute('aria-hidden', 'true');
    }catch(err){}
  }

  function disablePassiveIframes(){
    window.parent.document.querySelectorAll('iframe').forEach(frame=>{
      const rect = frame.getBoundingClientRect();
      const height =
        rect.height ||
        frame.clientHeight ||
        Number(frame.getAttribute('height') || 0);
      if (height > 4) return;
      frame.setAttribute('tabindex', '-1');
      frame.setAttribute('aria-hidden', 'true');
    });
  }

  function getModeCards(){
    return Array.from(window.parent.document.querySelectorAll('.feature-card'))
      .filter(card=>{
        const style = window.parent.getComputedStyle(card);
        if (style.display === 'none' || style.visibility === 'hidden') return false;
        return card.offsetWidth > 0 || card.offsetHeight > 0;
      });
  }

  setTimeout(()=>{
    speakOnce(
      `material-mode:__INTRO_TOKEN__`,
      '강의 자료 분석입니다. 1번, 파일 업로드. 2번, 카메라 촬영. 숫자키 1 또는 2를 눌러 선택하세요. 백스페이스 를 누르면 홈으로 돌아갑니다.'
    );
  }, 500);

  function attachFocus(){
    disableOwnFrame();
    disablePassiveIframes();

    // 1. Buttons
    window.parent.document.querySelectorAll('button').forEach(b=>{
      if(b._rmA) return; b._rmA=true;
      b.setAttribute('tabindex', '-1');
      b.addEventListener('focus', ()=>{
        const t = b.innerText.trim();
        if(t.includes('파일 업로드'))   speak('일번, 파일 업로드 버튼입니다. 엔터를 눌러주세요.');
        if(t.includes('카메라 촬영'))   speak('이번, 카메라 촬영 버튼입니다. 엔터를 눌러주세요.');
        if(t.includes('분석 시작'))     speak('분석 시작 버튼입니다. 엔터를 눌러주세요.');
      });
    });

    // 2. Feature Cards
    window.parent.document.querySelectorAll('.feature-card').forEach(c=>{
      if(c._rmA)return; c._rmA=true;
      if(!c.getAttribute('tabindex')) c.setAttribute('tabindex', '0');
      c.addEventListener('focus',()=>{
        const title=c.querySelector('.feature-title').innerText.trim();
        if(title.includes('파일 업로드')) speak('일번, 파일 업로드 버튼입니다. 엔터를 눌러주세요.');
        else if(title.includes('카메라 촬영')) speak('이번, 카메라 촬영 버튼입니다. 엔터를 눌러주세요.');
        else speak(title + ' 모드를 선택했습니다. 엔터를 누르면 시작합니다.');
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
  }

  // Focus Trapping
  function handleTab(e) {
    if (e.key !== 'Tab') return;
    const cards = getModeCards();
    if (cards.length === 0) return;

    e.preventDefault();
    e.stopPropagation();

    const active = window.parent.document.activeElement;
    const currentIndex = cards.indexOf(active);
    if (currentIndex === -1) {
      (e.shiftKey ? cards[cards.length - 1] : cards[0]).focus();
      return;
    }

    const nextIndex = e.shiftKey
      ? (currentIndex - 1 + cards.length) % cards.length
      : (currentIndex + 1) % cards.length;
    cards[nextIndex].focus();
  }
  function bindTabHandler(){
    try{
      if(window.parent._rmTabHandler){
        window.parent.document.removeEventListener('keydown', window.parent._rmTabHandler);
      }
      window.parent._rmTabHandler = handleTab;
      window.parent.document.addEventListener('keydown', window.parent._rmTabHandler);
    }catch(err){}

    document.removeEventListener('keydown', handleTab);
    document.addEventListener('keydown', handleTab);
  }

  const obs = new MutationObserver(attachFocus);
  obs.observe(window.parent.document.body, {childList:true, subtree:true});
  attachFocus();
  bindTabHandler();
  setTimeout(attachFocus, 150);

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

_UPLOAD_TEMPLATE = """
<script>
(function(){
__SPEAK_FN__

  function disableOwnFrame(){
    try{
      if(!window.frameElement) return;
      window.frameElement.setAttribute('tabindex', '-1');
      window.frameElement.setAttribute('aria-hidden', 'true');
    }catch(err){}
  }

  function disablePassiveIframes(){
    window.parent.document.querySelectorAll('iframe').forEach(frame=>{
      const rect = frame.getBoundingClientRect();
      const height =
        rect.height ||
        frame.clientHeight ||
        Number(frame.getAttribute('height') || 0);
      if (height > 4) return;
      frame.setAttribute('tabindex', '-1');
      frame.setAttribute('aria-hidden', 'true');
    });
  }

  setTimeout(()=>{
    speakOnce(
      `material-upload:__INTRO_TOKEN__`,
      '파일 업로드 모드입니다. 탭 키를 눌러 파일 선택 버튼으로 이동하세요. 백스페이스 를 누르면 모드 선택으로 돌아갑니다.'
    );
  }, 400);

  let announced = false;
  const obs = new MutationObserver(()=>{
    if(announced) return;
    const fname = window.parent.document.querySelector('[data-testid="stFileUploaderFileName"]');
    if(!fname) return;
    announced = true;
    const name = fname.textContent.trim();
    speak(`${name} 파일이 선택되었습니다. 탭 키를 눌러 분석 시작 버튼으로 이동한 뒤 엔터를 눌러주세요.`, ()=>{
      const btns = window.parent.document.querySelectorAll('button');
      for(const b of btns){ if(b.innerText.includes('분석 시작')){ b.focus(); break; } }
    });
  });
  obs.observe(window.parent.document.body, {childList:true, subtree:true, characterData:true});

  function attachFocus(){
    disableOwnFrame();
    disablePassiveIframes();

    window.parent.document.querySelectorAll('button').forEach(b=>{
      if(b._rmA) return; b._rmA=true;
      b.addEventListener('focus', ()=>{
        const t = b.innerText.trim();
        if(t.includes('분석 시작')) speak('분석 시작 버튼입니다. 엔터를 눌러주세요.');
        if(t.includes('모드 선택')) speak('모드 선택으로 돌아가기 버튼입니다.');
      });
    });
  }
  const obs2 = new MutationObserver(attachFocus);
  obs2.observe(window.parent.document.body, {childList:true, subtree:true});
  attachFocus();
  setTimeout(attachFocus, 150);

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

_CAMERA_TEMPLATE = """
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

__SPEAK_FN__

  speakOnce(`material-camera:__INTRO_TOKEN__`, '카메라를 불러오는 중입니다. 잠시 기다려주세요.', async ()=>{
    try{
      const stream = await navigator.mediaDevices.getUserMedia({
        video:{ facingMode:'user', width:{ideal:1280}, height:{ideal:720} }
      });
      vid.srcObject = stream;
      status.textContent = '📷 문서를 화면에 맞춰주세요';
      speak('카메라가 준비되었습니다. 문서를 화면 가득 채운 뒤 스페이스를 눌러 촬영하세요.');
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
    speak('촬영되었습니다. 엔터를 누르면 분석을 시작합니다. 알을 누르면 다시 촬영합니다.');
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
    speak('다시 촬영합니다. 문서를 화면에 맞추고 스페이스를 눌러 촬영하세요.');
    window.parent.postMessage({type:'rm_camera', dataUrl:null}, '*');
  }

  function doUse(){
    speak('분석을 시작합니다. 잠시만 기다려 주세요');
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

_BRIDGE_JS = """
<script>
try{
  if(window.frameElement){
    window.frameElement.setAttribute('tabindex', '-1');
    window.frameElement.setAttribute('aria-hidden', 'true');
  }
}catch(err){}

window.addEventListener('message', function(e){
  if(!e.data) return;
  const btns = window.parent.document.querySelectorAll('button');

  if(e.data.type==='rm_go_mode'){
    for(const b of btns){ if(b.innerText.includes('모드 선택')){ b.click(); break; } }
  }

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


def _intro_js() -> str:
    intro_token = get_announcement_token('material:mode')
    return (
        _INTRO_TEMPLATE.replace('__SPEAK_FN__', make_speak_fn()).replace(
            '__INTRO_TOKEN__',
            str(intro_token),
        )
    )


def _upload_js() -> str:
    intro_token = get_announcement_token('material:upload')
    return (
        _UPLOAD_TEMPLATE.replace('__SPEAK_FN__', make_speak_fn()).replace(
            '__INTRO_TOKEN__',
            str(intro_token),
        )
    )


def _camera_html() -> str:
    intro_token = get_announcement_token('material:camera')
    return (
        _CAMERA_TEMPLATE.replace('__SPEAK_FN__', make_speak_fn()).replace(
            '__INTRO_TOKEN__',
            str(intro_token),
        )
    )


def _camera_result_js() -> str:
    intro_token = get_announcement_token('material:camera-result')
    return f"""
<script>
(function(){{
  {make_speak_fn()}
  setTimeout(()=>speakOnce('material-camera-result:{intro_token}','촬영된 이미지입니다. 엔터로 분석을 시작하거나 R키 로 다시 촬영하세요.'),400);
  function onKey(e){{
    const tag=e.target.tagName;
    if(tag==='INPUT'||tag==='TEXTAREA')return;
    if(e.code==='Enter'){{e.preventDefault();speak('분석을 시작합니다. 잠시만 기다려 주세요',()=>window.parent.postMessage({{type:'rm_cam_use'}},'*'));}}
    if(e.key.toLowerCase()==='r'){{speak('다시 촬영합니다.',()=>window.parent.postMessage({{type:'rm_cam_retry'}},'*'));}}
    if(e.key==='Backspace'){{e.preventDefault();speak('모드 선택으로 돌아갑니다.',()=>window.parent.postMessage({{type:'rm_cam_back'}},'*'));}}
  }}
  document.addEventListener('keydown',onKey);
  try{{window.parent.document.addEventListener('keydown',onKey);}}catch(err){{}}
}})();
</script>
"""


def render() -> None:
    if st.session_state.get('processing_error'):
        st.error(st.session_state.processing_error)

    for k, v in [('input_mode', None), ('camera_image', None)]:
        if k not in st.session_state:
            st.session_state[k] = v

    st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
    if st.button('ReadMate', key='back_material'):
        _reset()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="rm-page-title">📄 강의 자료 분석</div>', unsafe_allow_html=True
    )

    # 공통 브릿지 (항상 렌더)
    st.iframe(_BRIDGE_JS, height=1)

    if st.session_state.get('active_panel') == 'memo':
        render_result_panel()

    elif st.session_state.get('processing_job'):
        render_result_panel()
        _continue_processing()

    elif st.session_state.get('raw_text'):
        render_result_panel()

    else:
        # ── 모드 선택 ─────────────────────────────
        if st.session_state.input_mode is None:
            st.markdown(
                """
            <div class="kb-hint">
              <strong>1</strong> : 파일 업로드 &nbsp;|&nbsp;
              <strong>2</strong> : 카메라 촬영 &nbsp;|&nbsp;
              <strong>Backspace</strong> : 홈으로
            </div>
            """,
                unsafe_allow_html=True,
            )

            c1, c2 = st.columns(2, gap='large')
            with c1:
                st.markdown(
                    """
                <div class="feature-card" tabindex="0">
                  <div class="feature-icon">📁</div>
                  <div class="feature-title">파일 업로드</div>
                  <div class="feature-desc">PDF 또는 이미지 파일을<br>직접 올려 분석해요</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    '1번 · 파일 업로드', key='mode_upload', use_container_width=True
                ):
                    st.session_state.input_mode = 'upload'
                    st.rerun()

            with c2:
                st.markdown(
                    """
                <div class="feature-card" tabindex="0">
                  <div class="feature-icon">📷</div>
                  <div class="feature-title">카메라 촬영</div>
                  <div class="feature-desc">카메라로 문서를 촬영하면<br>바로 분석해드려요</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    '2번 · 카메라 촬영', key='mode_camera', use_container_width=True
                ):
                    st.session_state.input_mode = 'camera'
                    st.rerun()

            st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
            if st.button(
                '메모 패널 이동',
                key='move_material_memo_panel',
                use_container_width=True,
            ):
                st.session_state.active_panel = 'memo'
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

            st.iframe(_intro_js(), height=1)

        # ── 파일 업로드 모드 ──────────────────────
        elif st.session_state.input_mode == 'upload':
            st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
            if st.button('← 모드 선택', key='back_to_mode_upload'):
                st.session_state.input_mode = None
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown(
                """
            <div class="kb-hint">
              <strong>Tab</strong> : 버튼 이동 &nbsp;|&nbsp;
              <strong>Enter</strong> : 파일 탐색기 열기<br>
              파일 선택 후 → <strong>Tab</strong> 으로 분석 시작 →
              <strong>Enter</strong> &nbsp;|&nbsp;
              <strong>Backspace</strong> : 모드 선택으로
            </div>
            """,
                unsafe_allow_html=True,
            )

            uploaded = st.file_uploader(
                '강의 자료 (PDF · JPG · PNG · WEBP)',
                type=['pdf', 'jpg', 'jpeg', 'png', 'webp', 'bmp'],
                label_visibility='visible',
            )

            if uploaded:
                upload_data = None
                uploaded_bytes = uploaded.getvalue()
                if uploaded.name.lower().endswith('.pdf'):
                    st.info(f'📄 {uploaded.name}')
                    doc = fitz.open(stream=uploaded_bytes, filetype='pdf')
                    total = len(doc)
                    pidx = 0
                    if total > 1:
                        pidx = (
                            st.number_input(
                                f'분석할 페이지 (1~{total})', 1, total, 1, 1
                            )
                            - 1
                        )
                    pix = doc[pidx].get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
                    img = PILImage.frombytes(
                        'RGB', [pix.width, pix.height], pix.samples
                    )
                    st.image(
                        img,
                        caption=f'{pidx + 1}/{total} 페이지',
                        use_container_width=True,
                    )
                    upload_data = {
                        'file_name': uploaded.name,
                        'content': uploaded_bytes,
                    }
                else:
                    img = PILImage.open(io.BytesIO(uploaded_bytes)).convert('RGB')
                    st.image(img, caption='업로드된 이미지', use_container_width=True)
                    upload_data = {
                        'file_name': uploaded.name,
                        'content': uploaded_bytes,
                    }

                if upload_data and st.button(
                    '분석 시작', use_container_width=True, key='run_upload'
                ):
                    _tts_notify('분석을 시작합니다. 잠시만 기다려 주세요')
                    _queue_processing(upload_data['file_name'], upload_data['content'])
                    st.rerun()

            st.iframe(_upload_js(), height=1)

        # ── 카메라 촬영 모드 ──────────────────────
        elif st.session_state.input_mode == 'camera':
            st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
            if st.button('← 모드 선택', key='back_to_mode_camera'):
                st.session_state.input_mode = None
                st.session_state.camera_image = None
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

            if st.session_state.camera_image:
                st.markdown(
                    """
                <div class="kb-hint">
                  <strong>Enter</strong> : 분석 시작 &nbsp;|&nbsp;
                  <strong>R</strong> : 다시 촬영 &nbsp;|&nbsp;
                  <strong>Backspace</strong> : 모드 선택으로
                </div>
                """,
                    unsafe_allow_html=True,
                )

                img_data = st.session_state.camera_image
                _, b64 = img_data.split(',', 1)
                img = PILImage.open(io.BytesIO(base64.b64decode(b64))).convert('RGB')
                st.image(img, caption='촬영된 문서', use_container_width=True)

                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        '다시 촬영 (R)', use_container_width=True, key='cam_retry'
                    ):
                        st.session_state.camera_image = None
                        st.rerun()
                with c2:
                    if st.button(
                        '분석 시작 (Enter)', use_container_width=True, key='cam_use'
                    ):
                        _tts_notify('분석을 시작합니다. 잠시만 기다려 주세요')
                        _queue_processing('camera_capture.jpg', base64.b64decode(b64))
                        st.session_state.camera_image = None
                        st.rerun()

                # 키 이벤트 → postMessage
                st.iframe(_camera_result_js(), height=1)

            else:
                st.iframe(_camera_html(), height=680)

                cam_val = st.text_input(
                    'cam_bridge', key='cam_bridge', label_visibility='collapsed'
                )
                st.iframe(
                    """
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
""",
                    height=1,
                )

                if cam_val and cam_val.startswith('data:image'):
                    st.session_state.camera_image = cam_val
                    st.rerun()


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


def _run(file_name: str, content: bytes) -> bool:
    """문서 파일을 ReadingPipeline으로 분석한다."""
    try:
        with st.spinner('📄 자료 분석 중...'):
            result = analyze_content(file_name=file_name, content=content)
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
    st.session_state.analysis_source_name = file_name
    st.session_state.memo_autosaved_key = ''
    return True


def _queue_processing(file_name: str, content: bytes) -> None:
    """문서 분석 작업을 세션 상태에 적재한다."""
    job_id = submit_analysis_job(
        file_name=file_name,
        content=content,
        voice_preset=st.session_state.get('selected_voice', 'JiYeong Kang'),
    )
    st.session_state.processing_job = {
        'job_id': job_id,
        'input_label': 'OCR 처리',
    }
    st.session_state.processing_step = 'analysis'
    st.session_state.processing_message = (
        '분석중입니다. OCR 처리와 요약을 준비하고 있습니다.'
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
    st.session_state.analysis_source_name = file_name
    st.session_state.memo_autosaved_key = ''


# ── 진행 메시지별 TTS 문구 매핑 ─────────────────────────
_PROGRESS_TTS: dict[str, str] = {
    'OCR': '잠시만 기다려 주세요',
    'LLM': '잠시만 기다려 주세요',
    'TTS': '잠시만 기다려 주세요',
}
_last_tts_msg: dict = {}  # fragment 재진입마다 중복 재생 방지


@st.fragment(run_every='1.0s')
def _render_processing_status(job_id: str):
    """진행 상황을 깜빡임 없이 업데이트하기 위한 프래그먼트."""
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
        # 진행 중: 테마색 스피너 + 진행 메시지 + 반복 TTS
        current_msg = get_analysis_job_progress(job_id)

        # 단계가 바뀔 때 TTS 문구 결정
        tts_msg = next(
            (v for k, v in _PROGRESS_TTS.items() if k in current_msg),
            '잠시만 기다려 주세요',
        )
        step_changed = _last_tts_msg.get(job_id) != tts_msg
        if step_changed:
            _last_tts_msg[job_id] = tts_msg

        safe_msg = tts_msg.replace("'", "\\'")
        # step_changed 이면 즉시 1회 재생 후 interval 시작
        st.iframe(
            f"""
<script>
(function() {{
  {make_speak_fn()}

  // 이전 interval 제거 (fragment 재진입마다 새로 등록)
  if (window._rmTtsInterval) {{
    clearInterval(window._rmTtsInterval);
    window._rmTtsInterval = null;
  }}

  // 단계 변경 시 즉시 1회 재생
  {'speak("' + safe_msg + '", null, {priority:"high"});' if step_changed else ''}

  // 8초마다 반복 재생
  window._rmTtsInterval = setInterval(() => speak('{safe_msg}', null, {{priority:'high'}}), 8000);
}})();
</script>
""",
            height=1,
        )

        st.markdown(
            f"""
            <div class="rm-progress-wrap">
                <div class="rm-progress-dots">
                    <span></span><span></span><span></span>
                </div>
                <div class="rm-progress-msg">{current_msg}</div>
            </div>
            <style>
                .rm-progress-wrap {{
                    display: flex;
                    align-items: center;
                    gap: 14px;
                    padding: 1rem 1.4rem;
                    background: var(--surface, #fff8f4);
                    border: 1.5px solid var(--border, #d4b8a8);
                    border-left: 4px solid var(--accent, #c05a3a);
                    border-radius: 16px;
                    margin-bottom: .6rem;
                    box-shadow: 0 2px 12px rgba(100,60,40,.07);
                }}
                .rm-progress-dots {{
                    display: flex;
                    align-items: center;
                    gap: 5px;
                    flex-shrink: 0;
                }}
                .rm-progress-dots span {{
                    display: inline-block;
                    width: 8px; height: 8px;
                    border-radius: 50%;
                    background: var(--accent, #c05a3a);
                    animation: rm-bounce 1.2s ease-in-out infinite;
                }}
                .rm-progress-dots span:nth-child(2) {{ animation-delay: .2s; }}
                .rm-progress-dots span:nth-child(3) {{ animation-delay: .4s; }}
                @keyframes rm-bounce {{
                    0%, 80%, 100% {{ transform: scale(.6); opacity: .4; }}
                    40%            {{ transform: scale(1.0); opacity: 1; }}
                }}
                .rm-progress-msg {{
                    font-family: var(--font-body, 'Gowun Dodum', sans-serif);
                    font-size: .97rem;
                    font-weight: 700;
                    color: var(--text, #1a1a1a);
                    word-break: keep-all;
                }}
            </style>
        """,
            unsafe_allow_html=True,
        )

    else:
        # 완료: interval 중단 + 완료 안내
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
    """세션에 적재된 문서 분석 작업을 실행한다."""
    job = st.session_state.get('processing_job')
    if not job:
        return
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
        'input_mode',
        'camera_image',
        'pipeline_warnings',
        'processing_error',
        'processing_job',
        'processing_step',
        'processing_message',
        'summary_play_key',
        'summary_play_token',
        'qa_answer_play_token',
        'analysis_source_name',
        'memo_autosaved_key',
    ]:
        st.session_state[k] = (
            None
            if k
            in (
                'audio_bytes',
                'audio_mime',
                'audio_file_name',
                'feature',
                'input_mode',
                'camera_image',
                'processing_job',
                'processing_step',
            )
            else []
            if k in ('quiz', 'memo_keywords', 'qa_history', 'pipeline_warnings')
            else False
            if k == 'qa_new_answer'
            else ''
            if k == 'processing_error'
            else 'summary'
            if k == 'active_panel'
            else 0
            if k in ('summary_play_token', 'qa_answer_play_token')
            else ''
        )
