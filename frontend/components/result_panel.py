import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from components.tts_panel     import render_tts_panel
from components.summary_panel import render_summary_panel
from components.qa_panel      import render_qa_panel
from components.quiz_panel    import render_quiz_panel


def render_result_panel():
    if "active_panel" not in st.session_state:
        st.session_state.active_panel = "summary"
    if "qa_new_answer" not in st.session_state:
        st.session_state.qa_new_answer = False

    render_tts_panel()

    panel = st.session_state.active_panel
    if panel == "summary":
        render_summary_panel()
    elif panel == "qa":
        render_qa_panel()
    elif panel == "quiz":
        render_quiz_panel()
