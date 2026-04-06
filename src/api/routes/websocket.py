"""
LLM 서버 WebSocket 엔드포인트 (양방향).
WS /ws/chat — 연결을 유지하며 여러 요청/응답 처리
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.llm_factory import get_llm
from api.schemas import LLMResponse, WSRequest, WSResponse
from models.schemas import TaskType

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket('/ws/chat')
async def ws_chat(websocket: WebSocket) -> None:
    """
    WebSocket 양방향 LLM 채팅 엔드포인트.
    클라이언트는 JSON 메시지를 보내고, 서버는 결과를 JSON으로 응답한다.

    메시지 형식:
        {"task": "summarize" | "qa", "text": "...", "question": "..."}

    응답 형식:
        {"task": "...", "result": {...}, "error": null}
    """
    await websocket.accept()
    logger.info('[ws] client connected: %s', websocket.client)

    try:
        while True:
            raw = await websocket.receive_text()
            response = _handle_message(raw)
            await websocket.send_text(response.model_dump_json())
    except WebSocketDisconnect:
        logger.info('[ws] client disconnected: %s', websocket.client)


def _handle_message(raw: str) -> WSResponse:
    """
    WebSocket 메시지를 파싱하고 LLM을 호출해 WSResponse를 반환한다.

    Args:
        raw: 클라이언트가 보낸 JSON 문자열

    Returns:
        WSResponse: 결과 또는 에러 메시지
    """
    try:
        req = WSRequest.model_validate(json.loads(raw))
    except Exception as exc:
        return WSResponse(task='unknown', error=f'요청 파싱 실패: {exc}')

    task_map = {
        'summarize': TaskType.SUMMARIZE,
        'qa': TaskType.QA,
    }
    task = task_map.get(req.task)
    if task is None:
        return WSResponse(
            task=req.task,
            error=f'알 수 없는 task: "{req.task}". 허용값: summarize, qa',
        )

    if not req.text.strip():
        return WSResponse(task=req.task, error='text가 비어 있습니다.')
    if task is TaskType.QA and not (req.question or '').strip():
        return WSResponse(task=req.task, error='qa task에는 question이 필요합니다.')

    try:
        result = get_llm().generate(req.text, task, req.question)
    except Exception as exc:
        logger.exception('[ws] llm failed')
        return WSResponse(task=req.task, error=str(exc))

    return WSResponse(
        task=req.task,
        result=LLMResponse(
            summary=result.summary,
            key_points=result.key_points,
            qa_answer=result.qa_answer,
            engine=result.engine,
        ),
    )
