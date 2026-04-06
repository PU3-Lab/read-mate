import streamlit as st

def inject_styles():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&family=Gowun+Dodum&family=Nanum+Gothic:wght@400;700;800&display=swap');

/* ── WCAG 2.1 AAA 기준 저시력자용 고대비 웜톤 테마 ── */
:root {
  --bg:         #faf5f0;   /* 순백 대신 따뜻한 크림 → 눈부심 감소 */
  --surface:    #edddd0;   /* 배경 대비 확실히 구분되는 베이지 */
  --surface2:   #e0ccbb;   /* 2단계 중첩 카드용 */
  --border:     #7a5540;   /* 배경 대비 6.5:1 AA+ */
  --accent:     #8c2e10;   /* 흰 배경 대비 7.2:1 AAA */
  --accent2:    #1a6b55;   /* 흰 배경 대비 7.1:1 AAA */
  --accent3:    #8c2e10;
  --text:       #1a0f0a;   /* 배경 대비 18:1 AAA */
  --text-muted: #3d2010;   /* 배경 대비 8.5:1 AAA */
  --radius:     16px;
  --shadow:     0 2px 16px rgba(80,40,20,.18);
  --font-head:  'Nunito', 'Gowun Dodum', sans-serif;
  --font-body:  'Gowun Dodum', 'Nunito', sans-serif;
}

html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: var(--font-body) !important;
}
[data-testid="stAppViewContainer"] > .main { background: var(--bg) !important; }
[data-testid="block-container"] { padding-top: 1.5rem !important; max-width: 860px !important; }
#MainMenu, footer, header { visibility: hidden !important; }
[data-testid="stToolbar"] { display: none !important; }

/* ── 배경 도트 패턴 ── */
[data-testid="stAppViewContainer"]::before {
  content: "";
  position: fixed; inset: 0;
  background-image: radial-gradient(circle, #d4b8a8 1px, transparent 1px);
  background-size: 28px 28px;
  opacity: .2; pointer-events: none; z-index: 0;
}

/* ── Header ── */
.rm-header {
  text-align: center;
  padding: 2rem 0 1.4rem;
  border-bottom: 2px solid var(--border);
  margin-bottom: 2rem;
  position: relative; z-index: 1;
}
.rm-logo {
  display: flex; align-items: center;
  justify-content: center; gap: .5rem; margin-bottom: .3rem;
}
.rm-logo-icon { font-size: 2.2rem; }
.rm-logo-text {
  font-family: var(--font-head);
  font-size: 2.4rem; font-weight: 900;
  color: var(--text);
}
.rm-logo-text .accent { color: var(--accent); }
.rm-tagline {
  color: var(--text-muted); font-size: .9rem;
  margin: 0; font-weight: 700;
}

/* ── Card ── */
.rm-card {
  background: transparent;
  border: none;
  border-radius: 0;
  padding: .4rem 0;
  margin-bottom: 1rem;
  box-shadow: none;
  position: relative; z-index: 1;
  display: flex; align-items: center;
  min-height: unset;
  border-left: 4px solid var(--accent);
  padding-left: 1rem;
}
.rm-card-title {
  font-family: 'Nanum Gothic', 'Apple SD Gothic Neo', '맑은 고딕', 'Malgun Gothic', sans-serif;
  font-size: 1.4rem; font-weight: 900;
  color: var(--accent);
  margin: 0;
  display: flex; align-items: center; gap: .5rem;
  letter-spacing: .01em;
  -webkit-font-smoothing: antialiased;
}

/* ── Summary card (타이틀+본문 묶음 칸) ── */
.rm-summary-card {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: 1.2rem 1.6rem 1.4rem;
  margin-bottom: 1.2rem;
  box-shadow: var(--shadow);
  border-left: 5px solid var(--accent);
}
.rm-summary-card .rm-card-title {
  margin-bottom: .7rem;
}
.rm-summary-card .rm-body {
  margin: 0;
  padding: 0;
}

/* ── Page title (강의녹음/자료 분석 헤더용) ── */
.rm-page-title {
  font-family: 'Nanum Gothic', 'Apple SD Gothic Neo', '맑은 고딕', 'Malgun Gothic', sans-serif;
  font-size: 1.4rem;
  font-weight: 900;
  color: var(--accent);
  display: flex;
  align-items: center;
  gap: .5rem;
  padding: .4rem 0 .4rem 1rem;
  border-left: 4px solid var(--accent);
  margin-bottom: 1rem;
  letter-spacing: .02em;
  -webkit-font-smoothing: antialiased;
}

/* ── Feature card ── */
.feature-card {
  background: var(--surface);
  border: 2px solid var(--border);
  border-radius: 20px;
  padding: 2rem 1.6rem;
  text-align: center;
  box-shadow: var(--shadow);
  transition: border-color .2s, transform .15s;
  position: relative; z-index: 1;
}
.feature-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(192,90,58,.12);
}
.feature-icon { font-size: 2.8rem; margin-bottom: .7rem; }
.feature-title {
  font-family: var(--font-head);
  font-size: 1.15rem; font-weight: 900;
  color: var(--text); margin-bottom: .4rem;
}
.feature-desc {
  font-size: 1rem; color: var(--text-muted);
  font-weight: 700; line-height: 1.7;
}

/* ── Keyboard hint ── */
.kb-hint {
  background: var(--surface2);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: .9rem 1.2rem;
  font-size: .96rem; font-weight: 700;
  color: var(--text-muted);
  line-height: 1.9; margin-bottom: .8rem;
  position: relative; z-index: 1;
}
.kb-hint strong { color: var(--accent); }

/* ── Buttons ── */
.stButton > button {
  background: var(--accent) !important;
  color: #ffffff !important;
  border: none !important;
  border-radius: 50px !important;
  font-family: var(--font-head) !important;
  font-weight: 800 !important; font-size: 1rem !important;
  padding: .75rem 1.8rem !important;
  box-shadow: 0 2px 8px rgba(140,46,16,.35) !important;
  transition: opacity .15s, transform .15s !important;
  letter-spacing: .01em !important;
}
.stButton > button:hover {
  opacity: .88 !important; transform: translateY(-1px) !important;
}
.stButton > button:disabled {
  background: #d4b8a8 !important;
  color: #6b5044 !important; box-shadow: none !important;
}
.btn-sec > button {
  background: var(--surface) !important;
  color: var(--text-muted) !important;
  border: 1.5px solid var(--border) !important;
  box-shadow: none !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [role="tablist"] {
  gap: 4px; background: var(--surface2); padding: 4px;
  border-radius: 50px; border: 1.5px solid var(--border);
}
[data-testid="stTabs"] [role="tab"] {
  font-family: var(--font-head) !important;
  color: var(--text-muted) !important;
  border-radius: 50px !important; padding: .3rem 1rem !important;
  font-size: .84rem !important; font-weight: 700 !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  background: var(--surface) !important;
  color: var(--accent) !important;
  box-shadow: 0 2px 6px rgba(192,90,58,.15) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploadDropzone"] {
  background: var(--surface2) !important;
  border: 2px dashed var(--border) !important;
  border-radius: var(--radius) !important;
}
[data-testid="stFileUploadDropzone"]:hover {
  border-color: var(--accent) !important;
}

/* ── Text input ── */
.stTextInput input {
  background: var(--surface2) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: 50px !important; color: var(--text) !important;
  font-family: var(--font-body) !important;
  font-size: .9rem !important; font-weight: 700 !important;
  padding: .5rem 1.1rem !important;
}
.stTextInput input:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(192,90,58,.12) !important;
}

/* ── Text area ── */
.stTextArea textarea {
  background: var(--surface2) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--radius) !important;
  color: var(--text) !important;
  font-family: var(--font-body) !important;
  font-size: .9rem !important; font-weight: 700 !important;
}
.stTextArea textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(192,90,58,.12) !important;
}

/* ── Body text ── */
.rm-body {
  font-size: 1.05rem; line-height: 1.95;
  color: var(--text); font-weight: 700;
}

/* ── Keyword chips ── */
.kw-chips { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .6rem; }
.kw-chip {
  background: var(--surface2);
  border: 1.5px solid var(--border);
  color: var(--accent);
  border-radius: 50px; padding: .3rem 1rem;
  font-size: .95rem; font-weight: 800;
  font-family: var(--font-head);
}

/* ── QA bubbles ── */
.qa-user {
  background: var(--accent); color: #ffffff;
  border-radius: 18px 18px 4px 18px;
  padding: .75rem 1.1rem; font-size: .9rem; font-weight: 700;
  margin-bottom: .4rem; max-width: 80%; margin-left: auto;
  line-height: 1.6;
}
.qa-ai {
  background: var(--surface2);
  border: 1.5px solid var(--border); color: var(--text);
  border-radius: 18px 18px 18px 4px;
  padding: .75rem 1.1rem; font-size: .9rem; font-weight: 700;
  margin-bottom: .8rem; max-width: 90%; line-height: 1.7;
}

/* ── Alerts ── */
[data-testid="stInfo"] {
  background: #eef6f4 !important;
  border: 1.5px solid #2e7d6b !important;
  border-radius: var(--radius) !important;
  color: var(--text) !important;
}
[data-testid="stSuccess"] {
  background: #eef6f4 !important;
  border: 1.5px solid #2e7d6b !important;
  border-radius: var(--radius) !important;
}
[data-testid="stWarning"] {
  background: #fff8f0 !important;
  border: 1.5px solid var(--accent) !important;
  border-radius: var(--radius) !important;
}
[data-testid="stError"] {
  background: #fdf0ed !important;
  border: 1.5px solid #a03020 !important;
  border-radius: var(--radius) !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
  background: var(--surface2) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--radius) !important;
}

/* ── Spinner ── */
.stSpinner > div { border-top-color: var(--accent) !important; }

/* ── Audio ── */
audio { width: 100% !important; border-radius: 50px !important; }

/* ── Divider ── */
.step-div {
  text-align: center; color: var(--border);
  font-size: 1.2rem; margin: .2rem 0;
}

/* ── Number input ── */
[data-testid="stNumberInput"] input {
  background: var(--surface2) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--radius) !important;
  color: var(--text) !important;
  font-weight: 700 !important;
}

/* ── Footer ── */
.rm-footer {
  text-align: center; color: var(--text-muted);
  font-size: .78rem; padding: 2rem 0 1rem;
  border-top: 2px solid var(--border);
  margin-top: 2.5rem; font-family: var(--font-body);
}
</style>
""", unsafe_allow_html=True)