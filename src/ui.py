"""Streamlit UI 컴포넌트 모듈."""

from __future__ import annotations

from pathlib import Path

import streamlit as st


def render_input_section() -> tuple[str, any]:
    """입력 방식 선택 및 이미지 수신 UI.

    Returns:
        (입력 방식, 입력 데이터) 튜플
        입력 방식: 'camera' | 'upload'
    """
    mode = st.radio('입력 방식', ['카메라 촬영', '파일 업로드'], horizontal=True)
    return ('camera', None) if mode == '카메라 촬영' else ('upload', None)


def render_ocr_result(text: str) -> None:
    """OCR 추출 텍스트 표시 (접기 가능)."""
    with st.expander('📝 OCR 추출 텍스트', expanded=False):
        st.text_area('', value=text, height=200, disabled=True)


def render_summary(summary: str) -> None:
    """요약문 표시."""
    st.subheader('📄 요약')
    st.write(summary)


def render_audio_player(audio_path: Path) -> None:
    """TTS 오디오 플레이어 표시."""
    st.subheader('🔊 음성 듣기')
    with open(audio_path, 'rb') as f:
        st.audio(f.read(), format='audio/wav')


def render_quiz(quiz: list[dict]) -> None:
    """퀴즈 인터페이스 표시.

    Args:
        quiz: [{"question": str, "options": list, "answer": int}]
    """
    st.subheader('🧠 퀴즈')
    for i, item in enumerate(quiz):
        user_answer = st.radio(
            f"Q{i + 1}. {item['question']}",
            options=item['options'],
            key=f'quiz_{i}',
        )
        if st.button('정답 확인', key=f'check_{i}'):
            correct = item['options'][item['answer']]
            if user_answer == correct:
                st.success('✅ 정답!')
            else:
                st.error(f'❌ 오답. 정답: {correct}')


def render_keywords(keywords: list[str]) -> None:
    """핵심 키워드 표시."""
    st.subheader('🔑 핵심 키워드')
    st.write(' · '.join(f'`{kw}`' for kw in keywords))
