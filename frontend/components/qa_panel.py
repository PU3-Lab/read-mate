import json
import logging

import streamlit as st
from speak_js import get_announcement_token, make_speak_fn

from pipelines import answer_question

logger = logging.getLogger(__name__)

_QA_HTML = """
<style>
html, body{
  margin:0;
  padding:0;
  width:100%;
  height:210px;
  overflow:hidden;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{
  background:transparent;
  font-family:'Gowun Dodum',sans-serif;
  --bg:         #faf5f0;
  --surface:    #edddd0;
  --surface2:   #e0ccbb;
  --border:     #7a5540;
  --accent:     #8c2e10;
  --accent2:    #1a6b55;
  --text:       #1a0f0a;
  --text-muted: #3d2010;
  overflow:hidden;
}
#wrap{
  width:100%;
  height:210px;
  overflow:hidden;
  background:var(--surface);
  border:2px solid var(--border);
  border-radius:20px;
  padding:1.2rem 1.2rem;
  text-align:center;
  outline:none;
  transition:all .15s ease-out;
  display:flex;
  flex-direction:column;
  justify-content:center;
}
#wrap:focus{
  border-color:var(--accent);
  box-shadow:0 10px 25px rgba(140,46,16,.2);
  background:var(--surface2);
}
#icon{
  font-size:2rem;
  margin-bottom:.35rem;
  line-height:1;
}
#icon.pulse{animation:pulse 1s infinite;}
@keyframes pulse{
  0%,100%{transform:scale(1);opacity:1;}
  50%{transform:scale(1.15);opacity:.7;}
}
#status{
  font-size:1rem;
  font-weight:800;
  color:var(--text);
  margin-bottom:.3rem;
  line-height:1.35;
}
#hint{
  font-size:.76rem;
  color:var(--text-muted);
  font-weight:700;
  line-height:1.5;
  margin-bottom:.9rem;
}
#send-btn{
  background:var(--accent);
  color:#fff;
  border:none;
  border-radius:50px;
  padding:.62rem 0;
  font-size:.9rem;
  font-weight:700;
  cursor:pointer;
  width:100%;
  box-shadow:0 3px 10px rgba(140,46,16,.3);
  flex-shrink:0;
}
#send-btn:hover{opacity:.88;}
</style>

<div id="wrap" tabindex="0">
  <div id="icon">🎤</div>
  <div id="status">Space 를 눌러 질문을 말씀하세요</div>
  <div id="hint">Space : 녹음 시작/중지 &nbsp;|&nbsp; Enter : 전송 &nbsp;|&nbsp; Backspace : 요약으로</div>
  <button id="send-btn">질문 전송 (Enter)</button>
</div>

<script>
(function(){
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, recording = false, transcript = '';

  const icon   = document.getElementById('icon');
  const status = document.getElementById('status');
  const btn    = document.getElementById('send-btn');

  __SPEAK_FN__

  function findParentTextarea(){
    const doc = window.parent.document;
    return (
      doc.querySelector('textarea[data-rmqa-visible="1"]')
      || doc.querySelector('textarea[aria-label="qa_text"]')
      || doc.querySelector('textarea[placeholder="질문을 말씀하시거나 직접 입력하세요"]')
    );
  }

  function setParentTextareaValue(value){
    const textarea = findParentTextarea();
    if(!textarea) return '';
    const setter = Object.getOwnPropertyDescriptor(
      window.parent.HTMLTextAreaElement.prototype,
      'value'
    )?.set;
    if(setter){
      setter.call(textarea, value);
    } else {
      textarea.value = value;
    }
    textarea.dispatchEvent(new Event('input', { bubbles:true }));
    textarea.dispatchEvent(new Event('change', { bubbles:true }));
    return textarea.value || '';
  }

  function getParentTextareaValue(){
    const textarea = findParentTextarea();
    return textarea ? (textarea.value || '') : '';
  }

  function findParentSendButton(){
    const doc = window.parent.document;
    return (
      doc.querySelector('button[data-rmqa-send="1"]')
      || Array.from(doc.querySelectorAll('button')).find(
        (button) => button.innerText && button.innerText.includes('전송하기')
      )
    );
  }

  function initRec(){
    if(!SR) return;
    rec = new SR();
    rec.lang = 'ko-KR';
    rec.continuous = true;
    rec.interimResults = true;

    rec.onresult = (e) => {
      let interim = '';
      transcript = '';
      for(let i = 0; i < e.results.length; i++){
        const t = e.results[i][0].transcript;
        e.results[i].isFinal ? (transcript += t) : (interim += t);
      }
      transcript = setParentTextareaValue(
        transcript + (interim ? ' ' + interim : '')
      );
    };

    rec.onend = () => {
      if(recording) rec.start();
    };

    rec.onerror = () => {
      setIdle();
      speak('마이크 오류가 발생했습니다.');
    };
  }

  function setIdle(){
    recording = false;
    icon.className = '';
    icon.textContent = '🎤';
    transcript = getParentTextareaValue().trim();
    status.textContent = transcript
      ? '질문을 확인한 뒤 전송하기 버튼을 누르세요'
      : 'Space 를 눌러 질문을 말씀하세요';
  }

  function setRec(){
    recording = true;
    icon.className = 'pulse';
    icon.textContent = '🔴';
    status.textContent = '녹음 중... Space 로 중지';
  }

  function toggle(){
    if(!SR){
      speak('이 브라우저는 음성 인식을 지원하지 않습니다.');
      return;
    }
    if(!rec) initRec();

    if(!recording){
      transcript = '';
      setParentTextareaValue('');
      rec.start();
      setRec();
      speak('녹음을 시작합니다.');
    } else {
      rec.stop();
      setIdle();
      speak('녹음이 중지되었습니다. 엔터를 눌러 전송하세요.');
    }
  }

  function send(){
    const question = getParentTextareaValue().trim();
    transcript = question;
    if(!question){
      speak('먼저 질문을 말씀해주세요.');
      return;
    }
    speak('질문을 전송합니다. 잠시 기다려주세요.');
    setParentTextareaValue(question);
    const button = findParentSendButton();
    if(button){
      setTimeout(() => button.click(), 50);
    }
  }

  btn.addEventListener('click', send);

  function onKey(e){
    const tag = e.target.tagName;
    if(tag === 'INPUT' || tag === 'TEXTAREA') return;

    if(e.code === 'Space'){
      e.preventDefault();
      toggle();
    }

    if(e.code === 'Enter'){
      e.preventDefault();
      send();
    }

    if(e.key === 'Backspace'){
      e.preventDefault();
      speak('요약으로 돌아갑니다.', () => {
        const btns = window.parent.document.querySelectorAll('button');
        for(const b of btns){
          if(b.innerText.includes('요약으로')){
            b.click();
            break;
          }
        }
      });
    }
  }

  document.addEventListener('keydown', onKey);
  try{
    window.parent.document.addEventListener('keydown', onKey);
  } catch(err){}

  setTimeout(()=>speakOnce(
    `qa-intro:__INTRO_TOKEN__`,
    '질의응답 화면입니다. 스페이스키 를 눌러 질문을 하고, 다시 스페이스키 로 중지한 뒤 엔터키 로 전송하세요. 백스페이스 를 누르면 요약화면 으로 돌아갑니다.'
  ),400);
})();
</script>
"""

_QA_DOM_BRIDGE_HTML = """
<script>
(function(){
  setInterval(() => {
    try {
      const doc = window.parent.document;

      const textareas = doc.querySelectorAll('textarea');
      for(const textarea of textareas){
        if(textarea.getAttribute('aria-label') === 'qa_text'){
          textarea.setAttribute('data-rmqa-visible', '1');
        }
      }

      const buttons = doc.querySelectorAll('button');
      for(const button of buttons){
        if(button.innerText && button.innerText.includes('전송하기')){
          button.setAttribute('data-rmqa-send', '1');
        }
      }
    } catch (e) {}
  }, 200);
})();
</script>
"""


def render_qa_panel():
    """질의응답 패널을 렌더링한다."""
    intro_token = get_announcement_token('result:qa')
    if 'qa_text' not in st.session_state:
        st.session_state.qa_text = ''
    if st.session_state.get('qa_clear_text'):
        st.session_state.pop('qa_text', None)
        st.session_state.qa_clear_text = False

    st.markdown(
        """
        <div class="rm-card">
          <div class="rm-card-title">💬 질의응답</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    history = st.session_state.get('qa_history', [])
    latest_answer = history[-1]['a'] if history else ''
    answer_token = int(st.session_state.get('qa_answer_play_token', 0))
    for item in history:
        st.markdown(
            f'<div class="qa-user">🙋 {item["q"]}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="qa-ai">🤖 {item["a"]}</div>',
            unsafe_allow_html=True,
        )

    if latest_answer and st.session_state.get('qa_new_answer'):
        _speak_answer(latest_answer, answer_token)
        # 여기서 즉시 False로 바꾸면 Streamlit이 리런하면서 iframe이 제거될 수 있음.
        # 다음 질문 시작 시점(_ask)에서 리셋하도록 변경함.

    qa_html = _QA_HTML.replace(
        '__SPEAK_FN__', make_speak_fn(allow_generation=True)
    ).replace('__INTRO_TOKEN__', str(intro_token))
    st.components.v1.html(qa_html, height=210)

    question = st.text_area(
        'qa_text',
        key='qa_text',
        height=100,
        placeholder='질문을 말씀하시거나 직접 입력하세요',
        label_visibility='collapsed',
    )

    c1, c2 = st.columns([5, 2])
    with c1:
        st.caption('질문 입력 후 전송하기 버튼을 누르세요.')
    with c2:
        if st.button('전송하기', key='qa_send', width='stretch') and question.strip():
            _ask(question.strip())

    st.components.v1.html(_QA_DOM_BRIDGE_HTML, height=0)

    c3, c4 = st.columns(2)
    with c3:
        st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
        if st.button('←   요약', width='stretch', key='qa_back'):
            st.session_state.active_panel = 'summary'
            st.session_state.summary_play_token = (
                int(st.session_state.get('summary_play_token', 0)) + 1
            )
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
        if st.button('🗑️ 대화 초기화', width='stretch', key='qa_clear'):
            st.session_state.qa_history = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


def _speak_answer(answer: str, token: int) -> None:
    """새 답변을 TTS로 재생한다."""
    logger.info(f'[QA-Speak] 재생 호출됨 - Token: {token}')

    # 답변 재생은 최상위 우선순위(summary)로 설정
    speak_fn = make_speak_fn(allow_generation=True, priority='summary')
    answer_js = json.dumps(answer, ensure_ascii=False)
    hint_js = json.dumps(
        '다시 질문하려면 스페이스, 요약으로 돌아가려면 백스페이스 를 눌러주세요.'
    )

    # 고유 key를 부여하여 Streamlit이 매번 새로운 컴포넌트로 인식하게 함
    st.components.v1.html(
        f"""
<script>
(function(){{
  const owner = window.parent || window;
  owner.console.log('[QA-Answer-Component] JS 진입 성공 - Token:', {token});

  {speak_fn}

  // 이미 재생한 토큰인지 확인 (중복 재생 방지)
  if (owner.__rmLastPlayedToken === {token}) {{
    owner.console.log('[QA-Answer-Component] 중복 재생 방지됨 - Token:', {token});
    return;
  }}

  setTimeout(() => {{
    owner.console.log('[QA-Answer-Component] speak() 함수 호출');
    speak({answer_js}, () => {{
      owner.__rmLastPlayedToken = {token};
      owner.console.log('[QA-Answer-Component] 답변 재생 끝, 힌트 시작');
      setTimeout(() => speak({hint_js}), 300);
    }});
  }}, 200);
}})();
</script>
""",
        height=1,
    )


def _ask(question: str):
    """질문을 전송해 답변을 세션 히스토리에 추가한다."""
    st.session_state.qa_new_answer = False
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
    st.session_state.qa_answer_play_token = (
        int(st.session_state.get('qa_answer_play_token', 0)) + 1
    )
    st.session_state.qa_clear_text = True
    st.rerun()
