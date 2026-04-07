import streamlit as st
from speak_js import make_speak_fn

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
  text-align:left;line-height:1.7;min-height:120px;width:100%;
  white-space:pre-wrap;word-break:break-all;resize:none;outline:none;
  margin-bottom:.8rem;font-family:'Gowun Dodum',sans-serif;
}
#send-btn{
  background:linear-gradient(135deg,#ff7e5f,#f9a03f);color:#fff;
  border:none;border-radius:50px;padding:.6rem 0;
  font-size:.9rem;font-weight:700;cursor:pointer;width:100%;
  box-shadow:0 3px 10px rgba(255,126,95,.3);
}
#send-btn:hover{opacity:.88;}
</style>
<div id="wrap">
  <div id="icon">🎤</div>
  <div id="status">Space 를 눌러 질문을 말씀하세요</div>
  <div id="hint">Space : 녹음 시작/중지 &nbsp;|&nbsp; Enter : 전송 &nbsp;|&nbsp; Backspace : 요약으로</div>
  <textarea id="qbox" aria-label="질문 입력" placeholder="질문을 말씀하시거나 직접 입력하세요"></textarea>
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

  __SPEAK_FN__

  function initRec(){
    if(!SR)return;
    rec=new SR();rec.lang='ko-KR';rec.continuous=true;rec.interimResults=true;
    rec.onresult=(e)=>{
      let interim='';transcript='';
      for(let i=0;i<e.results.length;i++){
        const t=e.results[i][0].transcript;
        e.results[i].isFinal?(transcript+=t):(interim+=t);
      }
      qbox.value=transcript+(interim?' '+interim:'');
    };
    rec.onend=()=>{if(recording)rec.start();};
    rec.onerror=()=>{setIdle();speak('마이크 오류가 발생했습니다.');};
  }

  function setIdle(){
    recording=false;
    icon.className='';icon.textContent='🎤';
    status.textContent=qbox.value.trim()
      ? '질문을 확인한 뒤 전송하기 버튼을 누르세요'
      : 'Space 를 눌러 질문을 말씀하세요';
  }

  function setRec(){
    recording=true;
    icon.className='pulse';icon.textContent='🔴';
    status.textContent='녹음 중... Space 로 중지';
  }

  function toggle(){
    if(!SR){speak('이 브라우저는 음성 인식을 지원하지 않습니다.');return;}
    if(!rec)initRec();
    if(!recording){
      transcript='';
      qbox.value='';
      rec.start();
      setRec();
      speak('녹음을 시작합니다.');
    }
    else{
      rec.stop();
      setIdle();
      speak('녹음이 중지되었습니다. 전송하기 버튼을 누르세요.');
    }
  }

  function send(){
    const question=qbox.value.trim();
    transcript=question;
    if(!question){speak('먼저 질문을 말씀해주세요.');return;}
    speak('질문을 전송합니다. 잠시 기다려주세요.');
    window.parent.postMessage({type:'rm_qa',question},'*');
  }

  btn.addEventListener('click',send);
  qbox.addEventListener('input',()=>{
    transcript=qbox.value;
    if(!recording){
      status.textContent=transcript.trim()
        ? '질문을 확인한 뒤 전송하기 버튼을 누르세요'
        : 'Space 를 눌러 질문을 말씀하세요';
    }
  });

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
    """질의응답 패널을 렌더링한다."""
    if 'qa_bridge' not in st.session_state:
        st.session_state.qa_bridge = ''

    if st.session_state.qa_bridge.strip():
        queued_question = st.session_state.qa_bridge.strip()
        st.session_state.qa_bridge = ''
        _ask(queued_question)
        return

    st.markdown(
        """
    <div class="rm-card">
      <div class="rm-card-title">💬 질의응답</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    history = st.session_state.get('qa_history', [])
    for item in history:
        st.markdown(
            f'<div class="qa-user">🙋 {item["q"]}</div>', unsafe_allow_html=True
        )
        st.markdown(f'<div class="qa-ai">🤖 {item["a"]}</div>', unsafe_allow_html=True)

    # 마지막 답변 자동 낭독
    if history and st.session_state.get('qa_new_answer'):
        ans = history[-1]['a'].replace("'", "\\'").replace('\n', ' ')
        st.iframe(
            f"""
<script>
(function(){{
  {make_speak_fn()}
  setTimeout(()=>speak('{ans}',()=>{{
    setTimeout(()=>speak('다시 질문하려면 Space, 요약으로 돌아가려면 Backspace 를 눌러주세요.'),300);
  }}),300);
}})();
</script>
""",
            height=1,
        )
        st.session_state.qa_new_answer = False

    st.iframe(_QA_HTML.replace('__SPEAK_FN__', make_speak_fn()), height=340)
    st.iframe(_QA_BRIDGE_HTML, height=1)

    st.text_input('qa_bridge', key='qa_bridge', label_visibility='collapsed')
    
    st.components.v1.html(
        """
<script>
(function(){
  // React 렌더링 지연을 대비해 주기적으로 찾아서 지속적으로 숨깁니다.
  setInterval(() => {
    try {
      const inputs = window.parent.document.querySelectorAll('input[type="text"]');
      for(const input of inputs){
        if(input.getAttribute('aria-label') === 'qa_bridge'){
          input.setAttribute('data-rmqa', '1');
          
          let current = input;
          // 부모 요소들을 순회하며 공간을 차지하는 stTextInput 요소와 stElementContainer를 찾아서 아예 안 보이게 만듭니다.
          for (let i = 0; i < 7; i++) {
            if (!current) break;
            const testId = current.getAttribute('data-testid');
            if (testId === 'stTextInput' || testId === 'stElementContainer' || testId === 'stVerticalBlock') {
               if (current.style.display !== 'none') {
                   current.style.display = 'none';
                   current.style.height = '0';
                   current.style.margin = '0';
                   current.style.padding = '0';
               }
            }
            current = current.parentElement;
          }
        }
      }
    } catch (e) {}
  }, 200);
})();
</script>
""",
        height=0,
    )

    c3, c4 = st.columns(2)
    with c3:
        st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
        if st.button('←   요약', width='stretch', key='qa_back'):
            st.session_state.active_panel = 'summary'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with c4:
        st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
        if st.button('🗑️ 대화 초기화', width='stretch', key='qa_clear'):
            st.session_state.qa_history = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


def _ask(question: str):
    """질문을 전송해 답변을 세션 히스토리에 추가한다."""
    with st.spinner('답변 생성 중...'):
        try:
            answer = answer_question(
                question,
                st.session_state.get('raw_text', ''),
            )
        except Exception as exc:
            answer = f'오류: {exc}'
    st.session_state.qa_history.append({'q': question, 'a': answer})
    st.session_state.qa_new_answer = True
    st.rerun()
