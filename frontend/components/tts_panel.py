import base64

import streamlit as st
from speak_js import make_speak_fn


def render_tts_panel():
    audio = st.session_state.get('audio_bytes')
    audio_mime = st.session_state.get('audio_mime') or 'audio/wav'
    audio_file_name = st.session_state.get('audio_file_name') or 'readmate.wav'
    summary = st.session_state.get('summary', '')
    if not audio and not summary:
        return

    if audio:
        st.markdown(
            """
        <div class="rm-card">
          <div class="rm-card-title">🔊 음성으로 듣기</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
        b64 = base64.b64encode(audio).decode()
        st.iframe(
            f"""
            <style>
            #ap{{background:#fff8f2;border:1.5px solid #f0e0cc;border-radius:20px;padding:1.2rem;outline:none;}}
            #ap:focus{{border-color:#ff7e5f;box-shadow:0 0 0 4px rgba(255,126,95,.18);}}
            audio{{width:100%;border-radius:50px;margin-bottom:.5rem;}}
            #ap-hint{{font-size:.75rem;color:#b09a88;font-weight:700;text-align:center;}}
            </style>
            <div id="ap" tabindex="0" aria-label="오디오 플레이어. Space 로 재생 및 일시정지">
              <audio id="ae" controls src="data:{audio_mime};base64,{b64}"></audio>
              <div id="ap-hint">Space : 재생/일시정지 &nbsp;|&nbsp; R : 처음부터</div>
            </div>
            <script>
            (function(){{
              {make_speak_fn(priority='summary')}
              const a=document.getElementById('ae');
              a.playbackRate=(__rmOwner.__rmVoiceSpeed)||1.0;
              function ownAudio(){{
                claimAudio(a,'summary',Date.now());
              }}
              function onKey(e){{
                const tag=e.target.tagName;
                if(tag==='INPUT'||tag==='TEXTAREA')return;
                if(e.code==='Space'){{e.preventDefault();ownAudio();a.paused?a.play():a.pause();}}
                if(e.key.toLowerCase()==='r'){{ownAudio();a.currentTime=0;a.play();}}
              }}
              a.addEventListener('play',ownAudio);
              ownAudio();
              a.currentTime=0;
              a.play().catch(()=>{{}});
              document.addEventListener('keydown',onKey);
              try{{window.parent.document.addEventListener('keydown',onKey);}}catch(err){{}}
              window.addEventListener('beforeunload',()=>{{
                try{{
                  if(window.parent.__rmCurrentAudio===a) window.parent.__rmCurrentAudio=null;
                }}catch(err){{}}
              }});
              document.getElementById('ap').focus();
            }})();
            </script>
            """,
            height=110,
        )
        st.download_button(
            '⬇️ 음성 저장',
            data=audio,
            file_name=audio_file_name,
            mime=audio_mime,
            width='stretch',
        )

    elif summary:
        safe = summary.replace("'", "\\'").replace('\n', ' ')
        st.iframe(
            f"""
<script>
(function(){{
  {make_speak_fn(allow_generation=True)}
  setTimeout(()=>{{
    speak('{safe}');
  }},300);
}})();
</script>
""",
            height=1,
        )
