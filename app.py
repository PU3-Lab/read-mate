"""ReadMate — Streamlit 진입점."""

import streamlit as st

from src import input as inp
from src import preprocess, ui
from src.pipeline import Pipeline


@st.cache_resource
def get_pipeline() -> Pipeline:
    """파이프라인 초기화 (앱 실행 시 1회만 로드)."""
    return Pipeline.local()


def main() -> None:
    st.set_page_config(page_title='ReadMate', page_icon='📚', layout='wide')
    st.title('📚 ReadMate')
    st.caption('실물 책을 촬영하여 OCR · 요약 · 퀴즈 · 낭독을 제공하는 학습 보조 도구')

    # ── 세션 초기화 ───────────────────────────────────────
    for key in ('ocr_text', 'llm_result', 'audio_path'):
        if key not in st.session_state:
            st.session_state[key] = None

    # ── Step 1: 입력 ──────────────────────────────────────
    mode, _ = ui.render_input_section()
    image = inp.load_from_camera() if mode == 'camera' else inp.load_from_upload()

    if image is None:
        st.info('이미지를 입력하면 분석이 시작됩니다.')
        return

    # ── Step 2~5: 파이프라인 실행 ────────────────────────
    with st.spinner('분석 중...'):
        processed = preprocess.preprocess(image)
        result = get_pipeline().run(processed)

    # 세션 저장
    st.session_state['ocr_text'] = result['ocr_text']
    st.session_state['llm_result'] = result
    st.session_state['audio_path'] = result['audio_path']

    # ── Step 6: UI 출력 ───────────────────────────────────
    ui.render_ocr_result(result['ocr_text'])
    ui.render_summary(result['summary'])
    ui.render_audio_player(result['audio_path'])
    ui.render_quiz(result['quiz'])
    ui.render_keywords(result['keywords'])


if __name__ == '__main__':
    main()
