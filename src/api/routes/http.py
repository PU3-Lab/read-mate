"""
LLM 서버 HTTP 엔드포인트 (단방향).
POST /api/summarize — 요약·정리
POST /api/qa       — 질의응답
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from api.llm_factory import get_llm
from api.schemas import LLMResponse, QARequest, SummarizeRequest
from models.schemas import TaskType

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api')


@router.post('/summarize', response_model=LLMResponse)
def summarize(req: SummarizeRequest) -> LLMResponse:
    """
    텍스트를 받아 요약·핵심 정리 결과를 반환한다.

    Args:
        req: 요약 요청 (text)

    Returns:
        LLMResponse: 요약, 핵심 포인트, 엔진명
    """
    if not req.text.strip():
        raise HTTPException(status_code=422, detail='text가 비어 있습니다.')

    try:
        result = get_llm().generate(req.text, TaskType.SUMMARIZE)
    except Exception as exc:
        logger.exception('[http] summarize failed')
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return LLMResponse(
        summary=result.summary,
        key_points=result.key_points,
        qa_answer=result.qa_answer,
        engine=result.engine,
    )


@router.post('/qa', response_model=LLMResponse)
def qa(req: QARequest) -> LLMResponse:
    """
    텍스트와 질문을 받아 질의응답 결과를 반환한다.

    Args:
        req: QA 요청 (text, question)

    Returns:
        LLMResponse: 요약, 핵심 포인트, 질의응답 답변, 엔진명
    """
    if not req.text.strip():
        raise HTTPException(status_code=422, detail='text가 비어 있습니다.')
    if not req.question.strip():
        raise HTTPException(status_code=422, detail='question이 비어 있습니다.')

    try:
        result = get_llm().generate(req.text, TaskType.QA, req.question)
    except Exception as exc:
        logger.exception('[http] qa failed')
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return LLMResponse(
        summary=result.summary,
        key_points=result.key_points,
        qa_answer=result.qa_answer,
        engine=result.engine,
    )
