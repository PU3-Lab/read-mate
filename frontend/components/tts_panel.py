import base64

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import streamlit.components.v1 as components

def render_tts_panel():
    audio   = st.session_state.get("audio_bytes")
    summary = st.session_state.get("summary", "")
    if not audio and not summary:
        return

    if audio:
        st.markdown("""
        <div class="rm-card">
          <div class="rm-card-title">🔊 음성으로 듣기</div>
        </div>
        """, unsafe_allow_html=True)
        b64 = base64.b64encode(audio).decode()
        components.html(f"""
<style>
#ap{{background:#fff8f2;border:1.5px solid #f0e0cc;border-radius:20px;padding:1.2rem;outline:none;}}
#ap:focus{{border-color:#ff7e5f;box-shadow:0 0 0 4px rgba(255,126,95,.18);}}
audio{{width:100%;border-radius:50px;margin-bottom:.5rem;}}
#ap-hint{{font-size:.75rem;color:#b09a88;font-weight:700;text-align:center;}}
</style>
<div id="ap" tabindex="0" aria-label="오디오 플레이어. Space 로 재생 및 일시정지">
  <audio id="ae" controls autoplay src="data:audio/wav;base64,{b64}"></audio>
  <div id="ap-hint">Space : 재생/일시정지 &nbsp;|&nbsp; R : 처음부터</div>
</div>
<script>
const a=document.getElementById('ae');
function onKey(e){{
  const tag=e.target.tagName;
  if(tag==='INPUT'||tag==='TEXTAREA')return;
  if(e.code==='Space'){{e.preventDefault();a.paused?a.play():a.pause();}}
  if(e.key.toLowerCase()==='r'){{a.currentTime=0;a.play();}}
}}
document.addEventListener('keydown',onKey);
try{{window.parent.document.addEventListener('keydown',onKey);}}catch(err){{}}
document.getElementById('ap').focus();
</script>
""", height=110, scrolling=False)
        st.download_button("⬇️ 음성 저장 (.wav)", data=audio,
                           file_name="readmate.wav", mime="audio/wav",
                           use_container_width=True)

    elif summary:
        # 브라우저 TTS 자동 낭독 (MeloTTS 미연결 시 폴백)
        safe = summary.replace("'","\\'").replace("\n"," ")
        components.html(f"""
<script>
(function(){{
  setTimeout(()=>{{
    if(!window.speechSynthesis)return;
    window.speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance('{safe}');
    u.lang='ko-KR';u.rate=0.95;
    window.speechSynthesis.speak(u);
  }},300);
}})();
</script>
""", height=0)
