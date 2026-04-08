"""
LLM 서버 HTTP 엔드포인트 (단방향).
POST /api/summarize — 요약·정리
POST /api/qa       — 질의응답
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from api.schemas import (
    LLMResponse,
    QARequest,
    QuizEvaluateRequest,
    QuizEvaluateResponse,
    QuizItemSchema,
    QuizRequest,
    QuizResponse,
    SummarizeRequest,
)
from models.schemas import TaskType

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api')


@router.post('/summarize', response_model=LLMResponse)
def summarize(req: SummarizeRequest, request: Request) -> LLMResponse:
    """
    텍스트를 받아 요약·핵심 정리 결과를 반환한다.

    Args:
        req: 요약 요청 (text)
        request: FastAPI 요청 객체

    Returns:
        LLMResponse: 요약, 핵심 포인트, 엔진명
    """
    if not req.text.strip():
        raise HTTPException(status_code=422, detail='text가 비어 있습니다.')

    try:
        result = request.app.state.llm.generate(req.text, TaskType.SUMMARIZE)
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
def qa(req: QARequest, request: Request) -> LLMResponse:
    """
    텍스트와 질문을 받아 질의응답 결과를 반환한다.

    Args:
        req: QA 요청 (text, question)
        request: FastAPI 요청 객체

    Returns:
        LLMResponse: 요약, 핵심 포인트, 질의응답 답변, 엔진명
    """
    if not req.text.strip():
        raise HTTPException(status_code=422, detail='text가 비어 있습니다.')
    if not req.question.strip():
        raise HTTPException(status_code=422, detail='question이 비어 있습니다.')

    try:
        result = request.app.state.llm.generate(req.text, TaskType.QA, req.question)
    except Exception as exc:
        logger.exception('[http] qa failed')
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return LLMResponse(
        summary=result.summary,
        key_points=result.key_points,
        qa_answer=result.qa_answer,
        engine=result.engine,
    )


@router.post('/quiz', response_model=QuizResponse)
def quiz(req: QuizRequest, request: Request) -> QuizResponse:
    """
    요약 텍스트를 받아 퀴즈 10개를 생성해 반환한다.

    Args:
        req: 퀴즈 생성 요청 (summary)
        request: FastAPI 요청 객체

    Returns:
        QuizResponse: 퀴즈 문항 목록과 엔진명
    """
    if not req.summary.strip():
        raise HTTPException(status_code=422, detail='summary가 비어 있습니다.')

    try:
        result = request.app.state.quiz_llm.generate(req.summary, TaskType.QUIZ)
    except Exception as exc:
        logger.exception('[http] quiz failed')
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    quiz_items = [
        QuizItemSchema(
            question=item.question,
            options=item.options,
            answer_index=item.answer_index,
        )
        for item in (result.quiz or [])
    ]
    return QuizResponse(quiz=quiz_items, engine=result.engine)


@router.post('/quiz/evaluate', response_model=QuizEvaluateResponse)
def quiz_evaluate(req: QuizEvaluateRequest, request: Request) -> QuizEvaluateResponse:
    """
    사용자의 음성 답변을 채점하고 이유를 설명한다.

    Args:
        req: 채점 요청 (question, options, correct_index, user_answer)
        request: FastAPI 요청 객체

    Returns:
        QuizEvaluateResponse: 정오 여부, 설명, 엔진명
    """
    if not req.user_answer.strip():
        raise HTTPException(status_code=422, detail='user_answer가 비어 있습니다.')

    try:
        result = request.app.state.quiz_llm.evaluate_answer(
            question=req.question,
            options=req.options,
            correct_index=req.correct_index,
            user_answer=req.user_answer,
        )
    except Exception as exc:
        logger.exception('[http] quiz/evaluate failed')
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return QuizEvaluateResponse(
        correct=result.correct,
        explanation=result.explanation,
        engine=result.engine,
    )
