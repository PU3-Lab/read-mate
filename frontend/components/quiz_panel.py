import json

import streamlit as st
from speak_js import get_announcement_token, get_server_url, make_speak_fn


def render_quiz_panel():
    quiz_list = st.session_state.get('quiz', [])
    if not quiz_list:
        return

    intro_token = get_announcement_token('result:quiz')
    server_url = get_server_url()
    server_js = json.dumps(server_url)
    qj = json.dumps(quiz_list, ensure_ascii=False)
    speak_fn = make_speak_fn(allow_generation=True)

    st.markdown(
        """
    <div class="rm-card">
      <div class="rm-card-title">🧩 퀴즈</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
    <div class="kb-hint">
      <strong>Space</strong> : 시작 / 녹음 / 다음 &nbsp;|&nbsp;
      <strong>L</strong> : 문제 다시 듣기 &nbsp;|&nbsp;
      <strong>R</strong> : 처음부터 &nbsp;|&nbsp;
      <strong>Backspace</strong> : 요약으로
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.iframe(
        f"""
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:transparent;font-family:'Gowun Dodum',sans-serif;}}
#qw{{background:#fff8f2;border:2px solid #f0e0cc;border-radius:20px;padding:1.6rem 1.4rem;outline:none;}}
#qw:focus{{border-color:#ff7e5f;box-shadow:0 0 0 4px rgba(255,126,95,.18);}}
#qc{{font-size:.8rem;font-weight:700;color:#b09a88;margin-bottom:.3rem;}}
#qs{{font-size:.78rem;font-weight:700;color:#b09a88;margin-bottom:.4rem;min-height:1.1rem;}}
#qt{{font-size:1.05rem;font-weight:800;color:#3d2f24;margin-bottom:.8rem;line-height:1.6;}}
.op{{display:flex;align-items:center;gap:.7rem;background:#fff;border:2px solid #f0e0cc;
    border-radius:14px;padding:.5rem .9rem;margin-bottom:.35rem;
    font-size:.88rem;font-weight:700;color:#3d2f24;}}
.op.ok{{border-color:#43bfa8;background:#f0fdf9;color:#1a8a78;}}
.op.ng{{border-color:#f06060;background:#fff1f1;color:#c03030;}}
.on{{background:#f0e0cc;border-radius:8px;width:26px;height:26px;
    display:flex;align-items:center;justify-content:center;font-size:.8rem;font-weight:800;flex-shrink:0;}}
.op.ok .on{{background:#43bfa8;color:#fff;}}
.op.ng .on{{background:#f06060;color:#fff;}}
#mic{{font-size:2rem;text-align:center;margin:.5rem 0;}}
#mic.pulse{{animation:pulse 1s infinite;}}
@keyframes pulse{{0%,100%{{transform:scale(1);opacity:1;}}50%{{transform:scale(1.2);opacity:.7;}}}}
#trs{{font-size:.88rem;font-style:italic;color:#7a6a5a;min-height:1.2rem;
     text-align:center;margin:.4rem 0;border-radius:10px;padding:.3rem .6rem;
     background:#fff4ee;border:1px dashed #f0cbb0;}}
#fb{{font-size:.95rem;font-weight:800;text-align:center;margin:.5rem 0;min-height:1.3rem;}}
#fb.ok{{color:#43bfa8;}} #fb.ng{{color:#f06060;}}
#exp{{font-size:.88rem;color:#3d2f24;line-height:1.7;padding:.6rem .9rem;
     background:#fff;border-radius:12px;border:1.5px solid #f0e0cc;margin:.4rem 0;min-height:1.2rem;}}
.br{{display:flex;gap:.5rem;margin-top:.8rem;flex-wrap:wrap;}}
.btn{{flex:1;background:linear-gradient(135deg,#ff7e5f,#f9a03f);color:#fff;border:none;
     border-radius:50px;padding:.5rem 0;font-size:.85rem;font-weight:700;cursor:pointer;
     box-shadow:0 3px 10px rgba(255,126,95,.3);min-width:60px;}}
.btn.sec{{background:#fff;color:#b09a88;border:1.5px solid #f0e0cc;box-shadow:none;}}
.btn:disabled{{background:#ede4da;color:#b09a88;box-shadow:none;cursor:default;}}
#sc{{text-align:center;font-size:1.1rem;font-weight:800;color:#ff7e5f;margin-top:.8rem;display:none;}}
#ready-hint{{text-align:center;font-size:1rem;font-weight:800;color:#ff7e5f;
            padding:1rem;border:2px dashed #f0cbb0;border-radius:16px;margin:.5rem 0;}}
</style>

<div id="qw" tabindex="0">
  <div id="qc"></div>
  <div id="qs"></div>
  <div id="ready-hint">🎙 퀴즈를 시작할 준비가 되면<br><strong>스페이스바</strong>를 누르세요</div>
  <div id="qt" style="display:none"></div>
  <div id="ops" style="display:none"></div>
  <div id="mic" style="display:none">🎤</div>
  <div id="trs" style="display:none"></div>
  <div id="fb" style="display:none"></div>
  <div id="exp" style="display:none"></div>
  <div class="br">
    <button class="btn sec" id="re" style="display:none">다시 듣기 (L)</button>
    <button class="btn sec" id="rty" style="display:none">처음 (R)</button>
    <button class="btn sec" id="bck">요약으로 (Backspace)</button>
  </div>
  <div id="sc" aria-live="polite"></div>
</div>

<script>
(function(){{
  const Q = {qj};
  const SERVER = {server_js};
  const introToken = {intro_token};

  // phase: ready | speaking | idle | recording | evaluating | result | final
  let phase = 'ready', cur = 0, score = 0;
  let rec = null, transcript = '';

  {speak_fn}

  function speakSeq(arr, i, cb){{
    if(i >= arr.length){{ if(cb) cb(); return; }}
    speak(arr[i], () => speakSeq(arr, i+1, cb));
  }}

  function numKo(n){{
    if(n===1) return "\uc77c";
    if(n===2) return "\uc774";
    if(n===3) return "\uc0bc";
    if(n===4) return "\uc0ac";
    return String(n);
  }}

  // 문제 + 보기를 낭독 배열로 구성 (각 보기를 별도 항목으로 분리)
  function buildReadItems(q, prompt){{
    const items = [`문제 ${{cur+1}}. ${{q.q}}`];
    q.options.forEach((o, i) => items.push(`${{numKo(i+1)}}번, ${{o}}`));
    items.push(prompt || '스페이스바를 눌러 답변을 말씀하세요.');
    return items;
  }}

  function setStatus(t){{ document.getElementById('qs').textContent = t; }}
  function setMic(active){{
    const m = document.getElementById('mic');
    m.style.display = '';
    m.className = active ? 'pulse' : '';
    m.textContent = active ? '🔴' : '🎤';
  }}
  function hideMic(){{ document.getElementById('mic').style.display = 'none'; }}
  function setFeedback(t, cls){{
    const fb = document.getElementById('fb');
    fb.style.display = t ? '' : 'none';
    fb.textContent = t;
    fb.className = cls || '';
  }}
  function setExplanation(t){{
    const exp = document.getElementById('exp');
    exp.style.display = t ? '' : 'none';
    exp.textContent = t;
  }}
  function setTranscript(t){{
    const el = document.getElementById('trs');
    el.style.display = t ? '' : 'none';
    el.textContent = t ? `"${{t}}"` : '';
  }}

  function showReady(){{
    document.getElementById('ready-hint').style.display = '';
    document.getElementById('qt').style.display = 'none';
    document.getElementById('ops').style.display = 'none';
    document.getElementById('re').style.display = 'none';
    document.getElementById('rty').style.display = 'none';
    hideMic(); setFeedback('',''); setExplanation(''); setTranscript('');
    setStatus('스페이스바를 눌러 퀴즈를 시작하세요');
    document.getElementById('qc').textContent = '';
    document.getElementById('sc').style.display = 'none';
  }}

  function renderQ(){{
    phase = 'speaking';
    const q = Q[cur];
    document.getElementById('ready-hint').style.display = 'none';
    document.getElementById('qc').textContent = `문제 ${{cur+1}} / ${{Q.length}}`;
    document.getElementById('qt').textContent = q.q;
    document.getElementById('qt').style.display = '';
    document.getElementById('re').style.display = '';

    // render options (read-only)
    const ops = document.getElementById('ops');
    ops.innerHTML = '';
    q.options.forEach((o, i) => {{
      const d = document.createElement('div');
      d.className = 'op';
      d.innerHTML = `<span class="on">${{i+1}}</span>${{o}}`;
      ops.appendChild(d);
    }});
    ops.style.display = '';

    hideMic(); setFeedback('',''); setExplanation(''); setTranscript('');
    setStatus('🔊 문제 낭독 중...');

    speakSeq(buildReadItems(q, '스페이스바를 눌러 답변을 말씀하세요.'), 0, () => {{
      phase = 'idle';
      setMic(false);
      setStatus('🎤 스페이스바를 눌러 답변 녹음');
    }});
    document.getElementById('qw').focus();
  }}

  function startRecording(){{
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if(!SR){{
      speak('이 브라우저에서는 음성 인식이 지원되지 않습니다. Chrome을 사용해주세요.');
      return;
    }}
    phase = 'recording';
    transcript = '';
    setTranscript('');
    setMic(true);
    setStatus('🔴 녹음 중... 스페이스바를 눌러 중지');

    rec = new SR();
    rec.lang = 'ko-KR';
    rec.continuous = false;
    rec.interimResults = true;

    rec.onresult = (e) => {{
      let t = '';
      for(let i = e.resultIndex; i < e.results.length; i++){{
        t += e.results[i][0].transcript;
      }}
      transcript = t;
      setTranscript(t);
    }};
    rec.onerror = (e) => {{
      console.warn('[Quiz] STT error:', e.error);
      if(phase === 'recording'){{
        phase = 'idle';
        setMic(false);
        setStatus('🎤 인식 실패. 스페이스바를 눌러 다시 시도');
        speak('음성을 인식하지 못했습니다. 다시 시도해주세요.');
      }}
    }};
    rec.onend = () => {{
      if(phase === 'recording') submitAnswer();
    }};
    rec.start();
  }}

  function stopRecording(){{
    if(rec){{ try{{ rec.stop(); }}catch(e){{}} rec = null; }}
  }}

  async function submitAnswer(){{
    phase = 'evaluating';
    setMic(false);
    setStatus('⏳ 채점 중...');
    const q = Q[cur];

    if(!transcript.trim()){{
      phase = 'idle';
      setMic(false);
      setStatus('🎤 답변을 인식하지 못했습니다. 스페이스바로 다시 시도');
      speak('답변을 인식하지 못했습니다. 스페이스바를 눌러 다시 시도해주세요.');
      return;
    }}

    try{{
      const resp = await fetch(`${{SERVER}}/api/quiz/evaluate`, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
          question: q.q,
          options: q.options,
          correct_index: q.answer,
          user_answer: transcript,
        }}),
      }});
      if(!resp.ok) throw new Error(`HTTP ${{resp.status}}`);
      const data = await resp.json();
      showResult(data.correct, data.explanation, q);
    }}catch(err){{
      console.error('[Quiz] evaluate failed:', err);
      phase = 'idle';
      setMic(false);
      setStatus('🎤 서버 오류. 스페이스바로 다시 시도');
      speak('서버 연결에 실패했습니다. 다시 시도해주세요.');
    }}
  }}

  function showResult(correct, explanation, q){{
    phase = 'result';
    if(correct) score++;

    // highlight correct/wrong options
    document.querySelectorAll('.op').forEach((el, i) => {{
      if(i === q.answer) el.classList.add('ok');
    }});

    setFeedback(correct ? '✅ 정답!' : '❌ 오답', correct ? 'ok' : 'ng');
    setExplanation(explanation);

    const isLast = (cur === Q.length - 1);
    setStatus(isLast ? '스페이스바를 눌러 결과 확인' : '스페이스바를 눌러 다음 문제');

    speakSeq(
      [
        correct ? '정답입니다!' : '오답입니다.',
        explanation,
        isLast ? '스페이스바를 눌러 최종 결과를 확인하세요.' : '스페이스바를 눌러 다음 문제로 이동하세요.',
      ],
      0,
      null
    );
  }}

  function nextOrFinal(){{
    if(cur < Q.length - 1){{
      cur++;
      setFeedback('',''); setExplanation(''); setTranscript('');
      document.querySelectorAll('.op').forEach(el => el.className = 'op');
      renderQ();
    }}else{{
      finalScore();
    }}
  }}

  function finalScore(){{
    phase = 'final';
    document.getElementById('ready-hint').style.display = 'none';
    document.getElementById('qt').style.display = 'none';
    document.getElementById('ops').style.display = 'none';
    hideMic(); setFeedback('',''); setExplanation(''); setTranscript('');
    document.getElementById('qc').textContent = '퀴즈 완료';
    document.getElementById('rty').style.display = '';
    const sc = document.getElementById('sc');
    sc.style.display = 'block';
    sc.textContent = `🎯 ${{score}} / ${{Q.length}} 정답`;
    setStatus('R: 처음부터 | Backspace: 요약으로');
    speak(`퀴즈가 끝났습니다. ${{Q.length}}문제 중 ${{score}}개 정답입니다. R키를 누르면 처음부터, Backspace키를 누르면 요약으로 돌아갑니다.`);
  }}

  function goBack(){{
    speak('요약으로 돌아갑니다.', () => {{
      const btns = window.parent.document.querySelectorAll('button');
      for(const b of btns){{
        if(b.innerText.includes('요약으로')){{ b.click(); break; }}
      }}
    }});
  }}

  function onKey(e){{
    const tag = e.target.tagName;
    if(tag === 'INPUT' || tag === 'TEXTAREA') return;

    if(e.code === 'Space'){{
      e.preventDefault();
      if(phase === 'ready'){{
        cur = 0; score = 0;
        showReady();
        renderQ();
      }}else if(phase === 'idle'){{
        stopSpeak(false);
        startRecording();
      }}else if(phase === 'recording'){{
        stopRecording();
      }}else if(phase === 'result'){{
        nextOrFinal();
      }}
      return;
    }}

    if(e.key.toLowerCase() === 'l'){{
      if(phase === 'idle' || phase === 'speaking'){{
        phase = 'speaking';
        setStatus('🔊 문제 낭독 중...');
        const q = Q[cur];
        speakSeq(buildReadItems(q, '스페이스바를 눌러 답변하세요.'), 0,
          () => {{ phase = 'idle'; setMic(false); setStatus('🎤 스페이스바를 눌러 답변 녹음'); }});
      }}
    }}

    if(e.key.toLowerCase() === 'r'){{
      if(phase === 'final' || phase === 'ready'){{
        cur = 0; score = 0; phase = 'ready';
        showReady();
        setTimeout(() => renderQ(), 100);
      }}
    }}

    if(e.key === 'Backspace'){{ e.preventDefault(); goBack(); }}
  }}

  document.addEventListener('keydown', onKey);
  try{{ window.parent.document.addEventListener('keydown', onKey); }}catch(err){{}}

  document.getElementById('re').onclick = () => {{
    if(phase === 'idle' || phase === 'speaking'){{
      phase = 'speaking';
      const q = Q[cur];
      const optsTxt = q.options.map((o,i)=>`${{i+1}}번, ${{o}}`).join('. ');
      speakSeq([`문제 ${{cur+1}}. ${{q.q}}`, optsTxt, '스페이스바를 눌러 답변하세요.'], 0,
        () => {{ phase = 'idle'; setMic(false); setStatus('🎤 스페이스바를 눌러 답변 녹음'); }});
    }}
  }};
  document.getElementById('rty').onclick = () => {{ cur=0;score=0;phase='ready';showReady();setTimeout(()=>renderQ(),100); }};
  document.getElementById('bck').onclick = goBack;
  document.getElementById('qw').focus();

  // 진입 안내
  setTimeout(() => {{
    speakOnce(
      `quiz-intro:${{introToken}}`,
      '퀴즈를 시작할 준비가 되면 스페이스바를 누르세요.',
      null
    );
  }}, 400);
}})();
</script>
""",
        height=680,
    )

    st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
    if st.button('← 요약으로 돌아가기', width='stretch', key='quiz_back'):
        st.session_state.active_panel = 'summary'
        st.session_state.summary_play_token = (
            int(st.session_state.get('summary_play_token', 0)) + 1
        )
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
