"""Streamlit 프런트엔드용 백그라운드 분석 작업 실행기."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from pipelines import analyze_content

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix='readmate-ui')
_JOBS: dict[str, Future[dict[str, Any]]] = {}
_PROGRESS: dict[str, str] = {}


def submit_analysis_job(
    file_name: str,
    content: bytes,
    voice_preset: str = 'default',
) -> str:
    """분석 작업을 백그라운드로 제출하고 작업 ID를 반환한다."""
    job_id = str(uuid.uuid4())

    def on_progress(msg: str) -> None:
        _PROGRESS[job_id] = msg

    def run_job():
        try:
            return analyze_content(
                file_name=file_name,
                content=content,
                voice_preset=voice_preset,
                on_progress=on_progress,
            )
        finally:
            # Note: We don't pop _PROGRESS here yet,
            # so the UI can read the final status if needed.
            # It will be cleaned up in get_analysis_job_result/wait_for_analysis_job.
            pass

    _JOBS[job_id] = _EXECUTOR.submit(run_job)
    _PROGRESS[job_id] = '준비 중...'
    return job_id


def wait_for_analysis_job(
    job_id: str,
    poll_interval: float = 0.1,
) -> dict[str, Any]:
    """완료될 때까지 분석 작업을 기다리고 결과를 반환한다."""
    future = _JOBS[job_id]
    while not future.done():
        time.sleep(poll_interval)

    try:
        return future.result()
    finally:
        _JOBS.pop(job_id, None)
        _PROGRESS.pop(job_id, None)


def get_analysis_job_result(job_id: str) -> dict[str, Any] | None:
    """작업이 완료되었으면 결과를 반환하고, 아니면 None을 반환한다."""
    future = _JOBS.get(job_id)
    if not future:
        return None
    if not future.done():
        return None

    try:
        return future.result()
    finally:
        _JOBS.pop(job_id, None)
        _PROGRESS.pop(job_id, None)


def get_analysis_job_progress(job_id: str) -> str:
    """작업의 현재 진행 상황 메시지를 반환한다."""
    return _PROGRESS.get(job_id, '진행 정보를 찾을 수 없습니다.')
