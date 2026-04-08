"""
ReadMate Streamlit 진입점.
업로드 파일을 ReadingPipeline으로 전달해 추출, 요약/QA, TTS 결과를 표시한다.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from models.schemas import InputPayload, InputType, PipelineResult, PipelineStatus
from pipelines import create_default_reading_pipeline

SUPPORTED_INPUT_TYPES: dict[str, InputType] = {
    '.png': InputType.IMAGE,
    '.jpg': InputType.IMAGE,
    '.jpeg': InputType.IMAGE,
    '.webp': InputType.IMAGE,
    '.pdf': InputType.PDF,
    '.mp3': InputType.AUDIO,
    '.wav': InputType.AUDIO,
    '.m4a': InputType.AUDIO,
    '.flac': InputType.AUDIO,
}

UPLOAD_TYPES: list[str] = [
    'png',
    'jpg',
    'jpeg',
    'webp',
    'pdf',
    'mp3',
    'wav',
    'm4a',
    'flac',
]


@st.cache_resource(show_spinner='파이프라인 로드 중...')
def get_pipeline():
    """기본 ReadMate 파이프라인을 캐시해 재사용한다."""
    return create_default_reading_pipeline()


def infer_input_type(file_name: str) -> InputType:
    """
    파일 확장자 기준으로 입력 타입을 판별한다.

    Args:
        file_name: 업로드 파일 이름

    Returns:
        InputType: 파이프라인 입력 타입

    Raises:
        ValueError: 지원하지 않는 확장자일 때
    """
    suffix = Path(file_name).suffix.lower()
    input_type = SUPPORTED_INPUT_TYPES.get(suffix)
    if input_type is None:
        raise ValueError(f'지원하지 않는 파일 형식입니다: {suffix or "(확장자 없음)"}')
    return input_type


def build_input_payload(
    file_name: str,
    content: bytes,
    question: str,
    voice_preset: str,
) -> InputPayload:
    """
    업로드 파일 정보를 InputPayload로 변환한다.

    Args:
        file_name: 업로드 파일 이름
        content: 파일 원본 바이트
        question: 사용자 질문
        voice_preset: TTS 화자 프리셋

    Returns:
        InputPayload: 파이프라인 요청 객체
    """
    return InputPayload(
        input_type=infer_input_type(file_name),
        file_name=file_name,
        content=content,
        question=question.strip() or None,
        voice_preset=voice_preset.strip() or 'default',
    )


def render_result(result: PipelineResult) -> None:
    """
    파이프라인 결과를 Streamlit 컴포넌트로 출력한다.

    Args:
        result: 파이프라인 실행 결과
    """
    if result.status is PipelineStatus.FAILED:
        st.error('파이프라인 실행 실패')
        for warning in result.warnings:
            st.write(f'- {warning}')
        return

    st.success('처리 완료')

    if result.warnings:
        st.warning('\n'.join(result.warnings))

    st.subheader('추출 텍스트')
    st.text_area(
        'extracted_text',
        value=result.extracted_text,
        height=240,
        label_visibility='collapsed',
    )

    if result.llm_result is not None:
        st.subheader('요약')
        st.write(result.llm_result.summary)

        st.subheader('핵심 포인트')
        for key_point in result.llm_result.key_points:
            st.write(f'- {key_point}')

        if result.llm_result.qa_answer:
            st.subheader('질문 응답')
            st.write(result.llm_result.qa_answer)

    if result.tts_result is not None:
        audio_path = Path(result.tts_result.audio_path)
        if audio_path.exists():
            st.subheader('음성 결과')
            st.audio(audio_path.read_bytes())
            st.caption(
                f'voice={result.tts_result.voice_preset} | '
                f'engine={result.tts_result.engine}'
            )


def main() -> None:
    """Streamlit 앱을 렌더링한다."""
    st.set_page_config(page_title='ReadMate', page_icon='📚', layout='wide')
    st.title('ReadMate')
    st.write('이미지, PDF, 오디오를 업로드하면 추출 -> 요약/QA -> TTS까지 한 번에 처리합니다.')

    uploaded_file = st.file_uploader(
        '파일 업로드',
        type=UPLOAD_TYPES,
        help='이미지, PDF, 오디오 파일을 업로드하세요.',
    )
    question = st.text_input('질문', placeholder='비워두면 요약만 수행합니다.')
    voice_preset = st.text_input('Voice preset', value='default')

    if uploaded_file is None:
        st.info('파일을 올리면 파이프라인을 실행합니다.')
        return

    col1, col2 = st.columns([1, 4])
    with col1:
        run_clicked = st.button('실행', type='primary', use_container_width=True)
    with col2:
        st.caption(f'업로드 파일: {uploaded_file.name}')

    if not run_clicked:
        return

    try:
        payload = build_input_payload(
            file_name=uploaded_file.name,
            content=uploaded_file.getvalue(),
            question=question,
            voice_preset=voice_preset,
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    with st.spinner('파이프라인 실행 중...'):
        result = get_pipeline().run(payload)

    render_result(result)


if __name__ == '__main__':
    main()
