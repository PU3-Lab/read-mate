import base64
import json

import streamlit as st
from speak_js import get_announcement_token, make_speak_fn

from components.qa_panel import render_qa_panel
from components.quiz_panel import render_quiz_panel
from components.summary_panel import render_summary_panel
from services.memo_service import list_saved_memos, load_saved_memo, save_summary_memo


def render_result_panel() -> None:
    """현재 활성 결과 패널을 렌더링한다."""
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
    if 'analysis_source_name' not in st.session_state:
        st.session_state.analysis_source_name = ''
    if 'memo_autosaved_key' not in st.session_state:
        st.session_state.memo_autosaved_key = ''
    if 'selected_memo_id' not in st.session_state:
        st.session_state.selected_memo_id = ''
    if 'memo_play_token' not in st.session_state:
        st.session_state.memo_play_token = 0

    _autosave_current_summary_memo()

    if st.session_state.pipeline_warnings:
        st.warning('\n'.join(st.session_state.pipeline_warnings))

    if st.session_state.processing_step:
        return

    _render_active_panel()


def _render_active_panel() -> None:
    """선택된 결과 패널을 보여준다."""
    panel = st.session_state.active_panel
    if panel == 'summary':
        render_summary_panel()
    elif panel == 'qa':
        render_qa_panel()
    elif panel == 'quiz':
        render_quiz_panel()
    elif panel == 'memo':
        _render_memo_panel()


def _autosave_current_summary_memo() -> None:
    """현재 요약 결과를 메모로 한 번만 저장한다."""
    summary = str(st.session_state.get('summary', '')).strip()
    if not summary:
        return

    signature = _build_memo_signature()
    if signature == st.session_state.get('memo_autosaved_key'):
        return

    try:
        saved = save_summary_memo(
            summary=summary,
            key_points=st.session_state.get('memo_keywords', []),
            raw_text=st.session_state.get('raw_text', ''),
            audio_bytes=st.session_state.get('audio_bytes'),
            audio_mime=st.session_state.get('audio_mime'),
            audio_file_name=st.session_state.get('audio_file_name'),
            source_name=st.session_state.get('analysis_source_name', ''),
        )
    except Exception as exc:
        warning = f'메모 저장 실패: {exc}'
        warnings = list(st.session_state.get('pipeline_warnings', []))
        if warning not in warnings:
            warnings.append(warning)
            st.session_state.pipeline_warnings = warnings
        return

    st.session_state.memo_autosaved_key = signature
    st.session_state.selected_memo_id = saved['id']


def _build_memo_signature() -> str:
    """중복 저장 방지용 현재 요약 시그니처를 만든다."""
    audio_bytes = st.session_state.get('audio_bytes') or b''
    keywords = st.session_state.get('memo_keywords', [])
    return '\n'.join(
        [
            str(st.session_state.get('analysis_source_name', '')).strip(),
            str(st.session_state.get('summary', '')).strip(),
            str(st.session_state.get('raw_text', '')).strip(),
            str(st.session_state.get('audio_file_name', '')).strip(),
            str(st.session_state.get('audio_mime', '')).strip(),
            str(len(audio_bytes)),
            '|'.join(str(item).strip() for item in keywords if str(item).strip()),
        ]
    )


def _render_memo_panel() -> None:
    """저장된 메모 목록과 상세 내용을 렌더링한다."""
    memos = list_saved_memos()
    intro_token = get_announcement_token('result:memo-panel')

    st.markdown(
        """
<div class="rm-summary-card">
  <div class="rm-card-title">📝 메모 패널</div>
  <div class="rm-body" style="font-size:.92rem;">
    탭 키로 메모 목록을 이동할 수 있습니다. 메모 버튼에 포커스되면 제목을 읽어드리고,
    엔터를 누르면 메모를 선택한 뒤 저장된 음성을 재생합니다.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if not memos:
        st.info('저장된 메모가 아직 없습니다.')
        _render_memo_intro(intro_token, [])
        _render_memo_back_button()
        return

    selected_memo_id = _resolve_selected_memo_id(memos)
    button_specs: list[dict[str, str]] = []

    st.markdown(
        """
<div class="rm-card">
  <div class="rm-card-title">📚 저장 메모 목록</div>
</div>
""",
        unsafe_allow_html=True,
    )

    for index, memo in enumerate(memos, start=1):
        memo_id = str(memo['id'])
        title = str(memo['title'])
        created_at = _format_created_at(str(memo['created_at']))
        source_name = str(memo['source_name'] or '직접 저장한 메모')
        label = f'{index}번 메모 · {title}'

        button_specs.append(
            {
                'button_label': label,
                'spoken_label': (
                    f'{index}번 메모, {title}. '
                    f'원본 자료는 {source_name}이고 저장 시각은 {created_at}입니다. '
                    '엔터를 누르면 메모를 엽니다.'
                ),
            }
        )

        if st.button(label, key=f'memo_select_{memo_id}', use_container_width=True):
            st.session_state.selected_memo_id = memo_id
            st.session_state.memo_play_token = (
                int(st.session_state.get('memo_play_token', 0)) + 1
            )
            st.rerun()

        st.caption(
            f'원본 자료: {source_name} | 저장 시각: {created_at} | '
            f'음성 저장: {"있음" if memo["has_audio"] else "없음"}'
        )

    try:
        detail = load_saved_memo(selected_memo_id)
    except FileNotFoundError:
        st.warning('선택한 메모를 찾지 못했습니다. 다른 메모를 선택해 주세요.')
    else:
        _render_selected_memo_detail(detail)

    _render_memo_intro(intro_token, button_specs)
    _render_memo_back_button()


def _resolve_selected_memo_id(memos: list[dict[str, object]]) -> str:
    """현재 선택된 메모 ID를 보정한다."""
    selected_id = str(st.session_state.get('selected_memo_id', '')).strip()
    valid_ids = {str(memo['id']) for memo in memos}
    if selected_id in valid_ids:
        return selected_id

    latest_id = str(memos[0]['id'])
    st.session_state.selected_memo_id = latest_id
    return latest_id


def _render_selected_memo_detail(detail: dict[str, object]) -> None:
    """선택된 메모의 상세 정보와 저장된 음성을 표시한다."""
    title = str(detail['title'])
    created_at = _format_created_at(str(detail['created_at']))
    source_name = str(detail['source_name'] or '직접 저장한 메모')
    summary = str(detail['summary'])
    key_points = detail.get('key_points') or []
    memo_id = str(detail['id'])

    st.markdown(
        f"""
<div class="rm-summary-card">
  <div class="rm-card-title">🗂 선택된 메모</div>
  <div class="rm-body" style="font-size:.92rem;">
    <strong>제목</strong> {title}<br>
    <strong>원본 자료</strong> {source_name}<br>
    <strong>저장 시각</strong> {created_at}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
<div class="rm-summary-card">
  <div class="rm-card-title">🧾 메모 내용</div>
  <div class="rm-body">{summary}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if key_points:
        st.markdown(
            ''.join(
                [
                    '<div class="rm-summary-card"><div class="rm-card-title">🔖 핵심 포인트</div>',
                    '<ul class="rm-body" style="margin:0; padding-left:1.2rem;">',
                    ''.join(f'<li>{str(item)}</li>' for item in key_points),
                    '</ul></div>',
                ]
            ),
            unsafe_allow_html=True,
        )

    if detail.get('audio_bytes'):
        audio_bytes = detail['audio_bytes']
        audio_mime = str(detail.get('audio_mime') or 'audio/wav')
        st.markdown(
            """
<div class="rm-card">
  <div class="rm-card-title">🔊 저장된 음성</div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.audio(audio_bytes, format=audio_mime)
        _render_memo_audio_autoplay(audio_bytes, audio_mime)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            '메모 텍스트 다운로드',
            data=summary.encode('utf-8'),
            file_name=f'{memo_id}.txt',
            mime='text/plain',
            use_container_width=True,
            key=f'memo_text_download_{memo_id}',
        )
    with c2:
        if detail.get('audio_bytes'):
            st.download_button(
                '메모 음성 다운로드',
                data=detail['audio_bytes'],
                file_name=str(detail.get('audio_file_name') or f'{memo_id}.wav'),
                mime=str(detail.get('audio_mime') or 'audio/wav'),
                use_container_width=True,
                key=f'memo_audio_download_{memo_id}',
            )


def _render_memo_audio_autoplay(audio_bytes: bytes, audio_mime: str) -> None:
    """메모를 선택했을 때 저장된 음성을 한 번 자동 재생한다."""
    play_token = int(st.session_state.get('memo_play_token', 0))
    if not play_token:
        return

    audio_src = f'data:{audio_mime};base64,{base64.b64encode(audio_bytes).decode()}'
    st.iframe(
        f"""
<script>
(function() {{
  {make_speak_fn(priority='summary')}
  const playToken = {play_token};
  const owner = window.parent;
  if (!playToken || owner.__rmMemoPlayToken === playToken) return;
  owner.__rmMemoPlayToken = playToken;

  const audio = new Audio({json.dumps(audio_src)});
  audio.playbackRate = owner.__rmVoiceSpeed || 1.0;
  audio.onended = () => {{
    try {{
      if (owner.__rmCurrentAudio === audio) owner.__rmCurrentAudio = null;
    }} catch (err) {{}}
  }};
  audio.onerror = () => {{
    try {{
      if (owner.__rmCurrentAudio === audio) owner.__rmCurrentAudio = null;
    }} catch (err) {{}}
  }};
  claimAudio(audio, 'summary', Date.now());
  audio.play().catch(() => {{}});
}})();
</script>
""",
        height=1,
    )


def _render_memo_intro(
    intro_token: int,
    button_specs: list[dict[str, str]],
) -> None:
    """메모 목록 포커스 안내와 패널 안내 음성을 연결한다."""
    payload = json.dumps(button_specs, ensure_ascii=False)
    st.iframe(
        f"""
<script>
(function() {{
  {make_speak_fn(allow_generation=True, priority='high')}
  const specs = {payload};

  function visibleButtons() {{
    return Array.from(window.parent.document.querySelectorAll('button')).filter((btn) => {{
      const text = (btn.innerText || '').trim();
      if (!text) return false;
      const style = window.parent.getComputedStyle(btn);
      if (style.display === 'none' || style.visibility === 'hidden') return false;
      return btn.offsetWidth > 0 || btn.offsetHeight > 0;
    }});
  }}

  function bindMemoButtons() {{
    const buttons = visibleButtons();
    specs.forEach((spec) => {{
      const button = buttons.find((item) => (item.innerText || '').trim() === spec.button_label);
      if (!button || button._rmMemoBound) return;
      button._rmMemoBound = true;
      button.addEventListener('focus', () => speak(spec.spoken_label));
    }});
  }}

  bindMemoButtons();
  const observer = new MutationObserver(bindMemoButtons);
  observer.observe(window.parent.document.body, {{ childList: true, subtree: true }});

  setTimeout(() => {{
    speakOnce(
      `memo-panel:{intro_token}`,
      '메모 패널입니다. 탭 키로 메모 목록을 이동하고, 엔터를 눌러 메모를 선택하세요.'
    );
  }}, 250);
}})();
</script>
""",
        height=1,
    )


def _render_memo_back_button() -> None:
    """메모 패널에서 요약 패널로 돌아가는 버튼을 렌더링한다."""
    st.markdown('<div class="btn-sec">', unsafe_allow_html=True)
    if st.button('← 요약으로 돌아가기', use_container_width=True, key='memo_back'):
        st.session_state.active_panel = 'summary'
        st.session_state.summary_play_token = (
            int(st.session_state.get('summary_play_token', 0)) + 1
        )
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


def _format_created_at(created_at: str) -> str:
    """ISO 포맷 저장 시각을 화면 표시용 문자열로 변환한다."""
    if not created_at:
        return '-'
    return created_at.replace('T', ' ')[:16]
