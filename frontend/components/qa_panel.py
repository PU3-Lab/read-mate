import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import streamlit.components.v1 as components

from pipelines import answer_question


_QA_HTML = """
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:transparent;font-family:'Gowun Dodum',sans-serif;}
#wrap{
  background:#fff8f2;border:2px solid #f0cbb0;
  border-radius:20px;padding:1.8rem 1.6rem;text-align:center;
}
#icon{font-size:2.2rem;margin-bottom:.5rem;}
#icon.pulse{animation:pulse 1s infinite;}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1;}50%{transform:scale(1.15);opacity:.7;}}
#status{font-size:1rem;font-weight:800;color:#3d2f24;margin-bottom:.3rem;}
#hint{font-size:.78rem;color:#b09a88;font-weight:700;line-height:1.8;margin-bottom:1rem;}
#qbox{
  background:#fff;border:1.5px solid #f0e0cc;border-radius:14px;
  padding:.8rem 1rem;font-size:.9rem;font-weight:700;color:#3d2f24;
  text-align:left;line-height:1.7;min-height:50px;
  white-space:pre-wrap;word-break:break-all;
  display:none;margin-bottom:.8rem;
}
#send-btn{
  background:linear-gradient(135deg,#ff7e5f,#f9a03f);color:#fff;
  border:none;border-radius:50px;padding:.6rem 0;
  font-size:.9rem;font-weight:700;cursor:pointer;width:100%;
  box-shadow:0 3px 10px rgba(255,126,95,.3);display:none;
}
#send-btn:hover{opacity:.88;}
</style>
<div id="wrap">
  <div id="icon">🎤</div>
  <div id="status">Space 를 눌러 질문을 말씀하세요</div>
  <div id="hint">Space : 녹음 시작/중지 &nbsp;|&nbsp; Enter : 전송 &nbsp;|&nbsp; Backspace : 요약으로</div>
  <div id="qbox" aria-live="polite"></div>
  <button id="send-btn">질문 전송 (Enter)</button>
</div>
<script>
(function(){
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec=null, recording=false, transcript='';

  const icon   = document.getElementById('icon');
  const status = document.getElementById('status');
  const hint   = document.getElementById('hint');
  const qbox   = document.getElementById('qbox');
  const btn    = document.getElementById('send-btn');

  function speak(t,cb){
    window.speechSynthesis&&window.speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(t);
    u.lang='ko-KR';u.rate=1.0;
    if(cb)u.onend=cb;
    window.speechSynthesis&&window.speechSynthesis.speak(u);
  }

  function initRec(){
    if(!SR)return;
    rec=new SR();rec.lang='ko-KR';rec.continuous=true;rec.interimResults=true;
    rec.onresult=(e)=>{
      let interim='';transcript='';
      for(let i=0;i<e.results.length;i++){
        const t=e.results[i][0].transcript;
        e.results[i].isFinal?(transcript+=t):(interim+=t);
      }
      qbox.textContent=transcript+(interim?'...'+interim:'');
    };
    rec.onend=()=>{if(recording)rec.start();};
    rec.onerror=()=>{setIdle();speak('마이크 오류가 발생했습니다.');};
  }

  function setIdle(){
    recording=false;
    icon.className='';icon.textContent='🎤';
    status.textContent='Space 를 눌러 질문을 말씀하세요';
    if(transcript){qbox.style.display='block';btn.style.display='block';hint.style.display='none';}
  }

  function setRec(){
    recording=true;
    icon.className='pulse';icon.textContent='🔴';
    status.textContent='녹음 중... Space 로 중지';
    qbox.style.display='block';btn.style.display='none';
  }

  function toggle(){
    if(!SR){speak('이 브라우저는 음성 인식을 지원하지 않습니다.');return;}
    if(!rec)initRec();
    if(!recording){rec.start();setRec();speak('녹음을 시작합니다.');}
    else{rec.stop();setIdle();speak('녹음이 중지되었습니다. Enter 를 눌러 전송하세요.');}
  }

  function send(){
    if(!transcript.trim()){speak('먼저 질문을 말씀해주세요.');return;}
    speak('질문을 전송합니다. 잠시 기다려주세요.');
    window.parent.postMessage({type:'rm_qa',question:transcript.trim()},'*');
  }

  btn.addEventListener('click',send);

  function onKey(e){
    const tag=e.target.tagName;
    if(tag==='INPUT'||tag==='TEXTAREA')return;
    if(e.code==='Space'){e.preventDefault();toggle();}
    if(e.code==='Enter'){e.preventDefault();send();}
    if(e.key==='Backspace'){
      e.preventDefault();
      speak('요약으로 돌아갑니다.',()=>{
        const btns=window.parent.document.querySelectorAll('button');
        for(const b of btns){if(b.innerText.includes('요약으로')){b.click();break;}}
      });
    }
  }

  document.addEventListener('keydown',onKey);
  try{window.parent.document.addEventListener('keydown',onKey);}catch(err){}

  setTimeout(()=>speak(
    '질의응답 화면입니다. Space 를 눌러 질문을 하고, 다시 Space 로 중지한 뒤 Enter 로 전송하세요. Backspace 를 누르면 요약화면 으로 돌아갑니다.'
  ),400);
})();
</script>
"""

_QA_BRIDGE_HTML = """
<script>
window.addEventListener('message', function(e){
  if(!e.data || e.data.type!=='rm_qa' || !e.data.question) return;
  const inputs = window.parent.document.querySelectorAll('input[type="text"]');
  for(const input of inputs){
    if(input.getAttribute('data-rmqa')){
      input.value = e.data.question;
      input.dispatchEvent(new Event('input', {bubbles:true}));
      break;
    }
  }
});
</script>
"""


def render_qa_panel():
    if 'qa_bridge' not in st.session_state:
        st.session_state.qa_bridge = ''

    if st.session_state.qa_bridge.strip():
        st.session_state.qa_text = st.session_state.qa_bridge.strip()
        queued_question = st.session_state.qa_bridge.strip()
        st.session_state.qa_bridge = ''
        _ask(queued_question)
        return

    st.markdown("""
    <div class="rm-card">
      <div class="rm-card-title">💬 질의응답</div>
    </div>
    """, unsafe_allow_html=True)

    history = st.session_state.get("qa_history", [])
    for item in history:
        st.markdown(f'<div class="qa-user">🙋 {item["q"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="qa-ai">🤖 {item["a"]}</div>', unsafe_allow_html=True)

    # 마지막 답변 자동 낭독
    if history and st.session_state.get("qa_new_answer"):
        ans = history[-1]["a"].replace("'","\\'").replace("\n"," ")
        components.html(f"""
<script>
(function(){{
  function speak(t,cb){{
    window.speechSynthesis&&window.speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(t);u.lang='ko-KR';u.rate=1.0;
    if(cb)u.onend=cb;window.speechSynthesis&&window.speechSynthesis.speak(u);
  }}
  setTimeout(()=>speak('{ans}',()=>{{
    setTimeout(()=>speak('다시 질문하려면 Space, 요약으로 돌아가려면 Backspace 를 눌러주세요.'),300);
  }}),300);
}})();
</script>
""", height=0)
        st.session_state.qa_new_answer = False

    components.html(_QA_HTML, height=270, scrolling=False)
    components.html(_QA_BRIDGE_HTML, height=0)

    # 보조 텍스트 입력
    st.markdown('<div style="color:var(--text-muted);font-size:.8rem;font-weight:700;text-align:center;margin:.6rem 0 .3rem;">음성 인식이 안 될 경우 직접 입력</div>', unsafe_allow_html=True)
    st.text_input('qa_bridge', key='qa_bridge', label_visibility='collapsed')
    components.html("""
<script>
(function(){
  const inputs = window.parent.document.querySelectorAll('input[type="text"]');
  for(const input of inputs){
    if(input.getAttribute('aria-label') === 'qa_bridge'){
      input.setAttribute('data-rmqa', '1');
      input.style.position = 'absolute';
      input.style.opacity = '0';
      input.style.pointerEvents = 'none';
      input.style.height = '0';
    }
  }
})();
</script>
""", height=0)
    c1, c2 = st.columns([4,1])
    with c1:
        tq = st.text_input("직접 입력", placeholder="질문 입력 후 Enter...", label_visibility="collapsed", key="qa_text")
    with c2:
        if st.button("전송", key="qa_send", use_container_width=True):
            if tq.strip():
                _ask(tq.strip())

    c3, c4 = st.columns(2)
    with c3:
        st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
        if st.button("←   요약", use_container_width=True, key="qa_back"):
            st.session_state.active_panel = "summary"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with c4:
        st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
        if st.button("🗑️ 대화 초기화", use_container_width=True, key="qa_clear"):
            st.session_state.qa_history = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


def _ask(question: str):
    with st.spinner("답변 생성 중..."):
        try:
            answer = answer_question(
                question,
                st.session_state.get("raw_text", ""),
            )
        except Exception as exc:
            answer = f"오류: {exc}"
    st.session_state.qa_history.append({"q": question, "a": answer})
    st.session_state.qa_new_answer = True
    st.rerun()
