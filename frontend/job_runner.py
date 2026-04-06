"""Streamlit 프런트엔드용 백그라운드 분석 작업 실행기."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from pipelines import analyze_content

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix='readmate-ui')
_JOBS: dict[str, Future[dict[str, Any]]] = {}


def submit_analysis_job(
    file_name: str,
    content: bytes,
    voice_preset: str = 'default',
) -> str:
    """분석 작업을 백그라운드로 제출하고 작업 ID를 반환한다."""
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = _EXECUTOR.submit(
        analyze_content,
        file_name=file_name,
        content=content,
        voice_preset=voice_preset,
    )
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
