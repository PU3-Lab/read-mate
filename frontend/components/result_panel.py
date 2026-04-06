import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from components.qa_panel import render_qa_panel
from components.quiz_panel import render_quiz_panel
from components.summary_panel import render_summary_panel
from components.tts_panel import render_tts_panel


def render_result_panel():
    """현재 활성 결과 패널을 먼저 렌더링하고 TTS는 뒤에 배치한다."""
    if 'active_panel' not in st.session_state:
        st.session_state.active_panel = 'summary'
    if 'qa_new_answer' not in st.session_state:
        st.session_state.qa_new_answer = False
    if 'pipeline_warnings' not in st.session_state:
        st.session_state.pipeline_warnings = []
    if 'processing_step' not in st.session_state:
        st.session_state.processing_step = None
    if 'processing_message' not in st.session_state:
        st.session_state.processing_message = ''

    if st.session_state.pipeline_warnings:
        st.warning('\n'.join(st.session_state.pipeline_warnings))

    if st.session_state.processing_step:
        # 진행 상황은 lecture_material.py / lecture_audio.py의 fragment가 직접 렌더링함
        return 

    panel = st.session_state.active_panel

    if panel == 'summary':
        render_summary_panel()
    elif panel == 'qa':
        render_qa_panel()
    elif panel == 'quiz':
        render_quiz_panel()

    render_tts_panel()
