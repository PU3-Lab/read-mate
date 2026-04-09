"""
LLM 서버 HTTP/WebSocket 요청·응답 Pydantic 스키마.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    """요약 HTTP 요청."""

    text: str = Field(..., description='요약할 텍스트')


class QARequest(BaseModel):
    """질의응답 HTTP 요청."""

    text: str = Field(..., description='참고할 텍스트')
    question: str = Field(..., description='사용자 질문')


class LLMResponse(BaseModel):
    """HTTP / WebSocket 공통 응답."""

    summary: str
    key_points: list[str]
    qa_answer: str | None = None
    engine: str


class QuizRequest(BaseModel):
    """퀴즈 생성 HTTP 요청."""

    summary: str = Field(..., description='퀴즈를 생성할 요약 텍스트')


class QuizItemSchema(BaseModel):
    """퀴즈 문항."""

    question: str
    options: list[str]
    answer_index: int


class QuizResponse(BaseModel):
    """퀴즈 생성 응답."""

    quiz: list[QuizItemSchema]
    engine: str


class QuizEvaluateRequest(BaseModel):
    """퀴즈 채점 HTTP 요청."""

    question: str = Field(..., description='퀴즈 문제')
    options: list[str] = Field(..., description='보기 목록 (4개)')
    correct_index: int = Field(..., description='정답 인덱스 (0~3)')
    user_answer: str = Field(..., description='사용자 음성 답변 텍스트')


class QuizEvaluateResponse(BaseModel):
    """퀴즈 채점 응답."""

    correct: bool
    explanation: str
    engine: str


class WSRequest(BaseModel):
    """WebSocket 단일 메시지 요청."""

    task: str = Field(..., description='"summarize" 또는 "qa"')
    text: str
    question: str | None = None


class WSResponse(BaseModel):
    """WebSocket 단일 메시지 응답."""

    task: str
    result: LLMResponse | None = None
    error: str | None = None
