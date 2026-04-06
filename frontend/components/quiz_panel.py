import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import streamlit.components.v1 as components
import json


def render_quiz_panel():
    quiz_list = st.session_state.get("quiz", [])
    if not quiz_list:
        return

    st.markdown("""
    <div class="rm-card">
      <div class="rm-card-title">🧩 퀴즈</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="kb-hint">
      <strong>1~4</strong> : 보기 선택 &nbsp;|&nbsp;
      <strong>Enter</strong> : 제출 &nbsp;|&nbsp;
      <strong>N</strong> : 다음 문제<br>
      <strong>L</strong> : 문제 다시 듣기 &nbsp;|&nbsp;
      <strong>C</strong> : 선택 확인 &nbsp;|&nbsp;
      <strong>R</strong> : 처음부터 &nbsp;|&nbsp;
      <strong>Backspace</strong> : 요약으로
    </div>
    """, unsafe_allow_html=True)

    qj = json.dumps(quiz_list, ensure_ascii=False)
    h  = 280 + len(quiz_list[0]["options"]) * 64 + 100

    components.html(f"""
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:transparent;font-family:'Gowun Dodum',sans-serif;}}
#qw{{background:#fff8f2;border:2px solid #f0e0cc;border-radius:20px;padding:1.6rem 1.4rem;outline:none;}}
#qw:focus{{border-color:#ff7e5f;box-shadow:0 0 0 4px rgba(255,126,95,.18);}}
#qc{{font-size:.8rem;font-weight:700;color:#b09a88;margin-bottom:.3rem;}}
#qs{{font-size:.78rem;font-weight:700;color:#b09a88;margin-bottom:.4rem;min-height:1.1rem;}}
#qt{{font-size:1.05rem;font-weight:800;color:#3d2f24;margin-bottom:1rem;line-height:1.6;}}
.op{{display:flex;align-items:center;gap:.7rem;background:#fff;border:2px solid #f0e0cc;
    border-radius:14px;padding:.6rem .9rem;margin-bottom:.45rem;
    font-size:.9rem;font-weight:700;color:#3d2f24;transition:border-color .15s,background .15s;cursor:pointer;}}
.op.sel{{border-color:#ff7e5f;background:#fff4ee;}}
.op.ok {{border-color:#43bfa8;background:#f0fdf9;color:#1a8a78;}}
.op.ng {{border-color:#f06060;background:#fff1f1;color:#c03030;}}
.on{{background:#f0e0cc;border-radius:8px;width:28px;height:28px;
    display:flex;align-items:center;justify-content:center;font-size:.82rem;font-weight:800;flex-shrink:0;}}
.op.sel .on{{background:#ff7e5f;color:#fff;}}
.op.ok  .on{{background:#43bfa8;color:#fff;}}
.op.ng  .on{{background:#f06060;color:#fff;}}
#fb{{font-size:.95rem;font-weight:800;text-align:center;margin:.7rem 0;min-height:1.3rem;}}
#fb.ok{{color:#43bfa8;}} #fb.ng{{color:#f06060;}}
.br{{display:flex;gap:.5rem;margin-top:.8rem;flex-wrap:wrap;}}
.btn{{flex:1;background:linear-gradient(135deg,#ff7e5f,#f9a03f);color:#fff;border:none;
     border-radius:50px;padding:.55rem 0;font-size:.85rem;font-weight:700;cursor:pointer;
     box-shadow:0 3px 10px rgba(255,126,95,.3);min-width:60px;}}
.btn:disabled{{background:#ede4da;color:#b09a88;box-shadow:none;cursor:default;}}
.btn.sec{{background:#fff;color:#b09a88;border:1.5px solid #f0e0cc;box-shadow:none;}}
#sc{{text-align:center;font-size:1.1rem;font-weight:800;color:#ff7e5f;margin-top:.8rem;display:none;}}
</style>

<div id="qw" tabindex="0">
  <div id="qc"></div>
  <div id="qs"></div>
  <div id="qt" aria-live="polite"></div>
  <div id="ops"></div>
  <div id="fb" aria-live="assertive"></div>
  <div class="br">
    <button class="btn"     id="sub" disabled>제출 (Enter)</button>
    <button class="btn sec" id="re"          >다시 듣기 (L)</button>
    <button class="btn sec" id="nxt" style="display:none">다음 (N)</button>
    <button class="btn sec" id="rty" style="display:none">처음 (R)</button>
    <button class="btn sec" id="bck"         >요약으로 (Backspace)</button>
  </div>
  <div id="sc" aria-live="polite"></div>
</div>

<script>
(function(){{
  const Q={qj};
  let cur=0, sel=-1, done=false, score=0;

  // 숫자 -> 한글 서수 변환 (TTS 오독 방지)
  // 한자어 서수: 일, 이, 삼, 사 (보기 번호, 정답 번호)
  function numKo(n){{
    if(n===1) return "\uc77c";
    if(n===2) return "\uc774";
    if(n===3) return "\uc0bc";
    if(n===4) return "\uc0ac";
    return String(n);
  }}
  // 고유어 서수: 한, 두, 세, 네 (개수, 문제 수, 점수)
  function numNative(n){{
    if(n===1) return "\ud55c";
    if(n===2) return "\ub450";
    if(n===3) return "\uc138";
    if(n===4) return "\ub124";
    if(n===5) return "\ub2e4\uc12f";
    if(n===6) return "\uc5ec\uc12f";
    if(n===7) return "\uc77c\uacf1";
    if(n===8) return "\uc5ec\ub35f";
    if(n===9) return "\uc544\ud649";
    if(n===10) return "\uc5f4";
    return String(n);
  }}

  function speak(t,cb){{
    window.speechSynthesis&&window.speechSynthesis.cancel();
    if(!t){{if(cb)cb();return;}}
    const u=new SpeechSynthesisUtterance(t);
    u.lang='ko-KR';u.rate=1.0;
    u.onend=()=>{{if(cb)cb();}};
    u.onerror=()=>{{if(cb)cb();}};
    window.speechSynthesis&&window.speechSynthesis.speak(u);
  }}

  function speakQ(arr,i,cb){{
    if(i>=arr.length){{if(cb)cb();return;}}
    speak(arr[i],()=>speakQ(arr,i+1,cb));
  }}

  function setStatus(t){{document.getElementById('qs').textContent=t;}}

  function renderQ(){{
    const q=Q[cur];done=false;sel=-1;
    document.getElementById('qc').textContent=`문제 ${{cur+1}} / ${{Q.length}}`;
    document.getElementById('qt').textContent=q.q;
    document.getElementById('fb').textContent='';
    document.getElementById('fb').className='';
    document.getElementById('sc').style.display='none';
    document.getElementById('sub').disabled=true;
    document.getElementById('nxt').style.display='none';
    document.getElementById('rty').style.display='none';
    setStatus('');

    const ops=document.getElementById('ops');
    ops.innerHTML='';
    q.options.forEach((o,i)=>{{
      const d=document.createElement('div');
      d.className='op';
      d.setAttribute('aria-label',`${{numKo(i+1)}}번. ${{o}}`);
      d.innerHTML=`<span class="on">${{i+1}}</span>${{o}}`;
      d.onclick=()=>pick(i);
      ops.appendChild(d);
    }});
    readQ();
    document.getElementById('qw').focus();
  }}

  function readQ(){{
    const q=Q[cur];
    const opts=q.options.map((o,i)=>`${{numKo(i+1)}}번, ${{o}}`).join('. ');
    setStatus('🔊 문제 낭독 중...');
    speakQ([`문제 ${{cur+1}}. ${{q.q}}`, opts, '숫자키로 보기를 선택하세요.'], 0,
      ()=>setStatus('보기를 선택하세요'));
  }}

  function pick(i){{
    if(done)return;
    sel=i;
    document.querySelectorAll('.op').forEach((e,j)=>e.className='op'+(j===i?' sel':''));
    document.getElementById('sub').disabled=false;
    setStatus(`✔ ${{numKo(i+1)}}번 선택됨`);
    speak(`${{numKo(i+1)}}번 선택. ${{Q[cur].options[i]}}`);
  }}

  function submit(){{
    if(sel<0||done)return;
    done=true;
    const q=Q[cur],ok=(sel===q.answer);
    if(ok)score++;
    document.querySelectorAll('.op').forEach((e,i)=>{{
      if(i===q.answer)e.classList.add('ok');
      else if(i===sel&&!ok)e.classList.add('ng');
    }});
    document.getElementById('sub').style.display='none';
    const fb=document.getElementById('fb');
    const isLast=(cur===Q.length-1);
    if(ok){{
      fb.textContent='✅ 정답!';fb.className='ok';
      speakQ(['정답입니다!', isLast?null:'N 을 누르면 다음 문제입니다.'].filter(Boolean),0,
        ()=>{{if(isLast)setTimeout(finalScore,600);
             else{{document.getElementById('nxt').style.display='';setStatus('N 을 눌러 다음 문제로');}}}});
    }}else{{
      const ans=q.options[q.answer];
      fb.textContent=`❌ 오답. 정답: ${{numKo(q.answer+1)}}번`;fb.className='ng';
      speakQ([`오답입니다. 정답은 ${{numKo(q.answer+1)}}번, ${{ans}} 입니다.`,
              isLast?null:'N 을 누르면 다음 문제입니다.'].filter(Boolean),0,
        ()=>{{if(isLast)setTimeout(finalScore,600);
             else{{document.getElementById('nxt').style.display='';setStatus('N 을 눌러 다음 문제로');}}}});
    }}
  }}

  function finalScore(){{
    const s=document.getElementById('sc');
    s.style.display='block';
    s.textContent=`🎯 ${{score}} / ${{Q.length}} 정답`;
    document.getElementById('rty').style.display='';
    setStatus('퀴즈 완료');
    speak(`퀴즈가 끝났습니다. ${{numNative(Q.length)}} 문제 중 ${{numNative(score)}} 개 정답입니다. R 을 누르면 처음부터, Backspace 를 누르면 요약으로 돌아갑니다.`);
  }}

  function goBack(){{
    speak('요약으로 돌아갑니다.',()=>{{
      const btns=window.parent.document.querySelectorAll('button');
      for(const b of btns){{if(b.innerText.includes('요약으로')){{b.click();break;}}}}
    }});
  }}

  function onKey(e){{
    const tag=e.target.tagName;
    if(tag==='INPUT'||tag==='TEXTAREA')return;
    if(['1','2','3','4'].includes(e.key)){{const i=parseInt(e.key)-1;if(i<Q[cur].options.length)pick(i);}}
    if(e.code==='Enter'){{e.preventDefault();if(!done)submit();else if(cur<Q.length-1){{cur++;renderQ();}}}}
    if(e.key.toLowerCase()==='n'){{if(done&&cur<Q.length-1){{cur++;renderQ();}}else if(!done)speak('먼저 답을 제출해주세요.');}}
    if(e.key.toLowerCase()==='l'){{readQ();}}
    if(e.key.toLowerCase()==='c'){{
      if(sel<0)speak('아직 선택하지 않으셨습니다.');
      else speak(`현재 ${{numKo(sel+1)}}번, ${{Q[cur].options[sel]}} 선택 중입니다.`);
    }}
    if(e.key.toLowerCase()==='r'){{cur=0;score=0;renderQ();}}
    if(e.key==='Backspace'){{e.preventDefault();goBack();}}
  }}

  document.getElementById('sub').onclick=submit;
  document.getElementById('re' ).onclick=readQ;
  document.getElementById('nxt').onclick=()=>{{cur++;renderQ();}};
  document.getElementById('rty').onclick=()=>{{cur=0;score=0;renderQ();}};
  document.getElementById('bck').onclick=goBack;

  document.addEventListener('keydown',onKey);
  try{{window.parent.document.addEventListener('keydown',onKey);}}catch(err){{}}

  // 진입 안내 → 첫 문제
  setTimeout(()=>{{
    speakQ([
      `총 ${{numNative(Q.length)}} 문제입니다.`,
      '숫자키 1부터 4로 보기를 선택하고 Enter 로 제출하세요.',
      'L 로 문제 다시 듣기, C 로 선택 확인, Backspace 로 요약으로 돌아갑니다.',
      '지금부터 시작합니다.'
    ], 0, ()=>setTimeout(renderQ,400));
  }},400);
}})();
</script>
""", height=h, scrolling=False)

    st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
    if st.button("← 요약으로 돌아가기", use_container_width=True, key="quiz_back"):
        st.session_state.active_panel = "summary"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)