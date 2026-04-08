"""
ReadMate LLM 서버 HTTP/WebSocket 클라이언트.
Streamlit UI 및 테스트 스크립트에서 사용한다.
"""

from __future__ import annotations

import asyncio
import json

import requests
import websockets

from api.schemas import LLMResponse, WSResponse

DEFAULT_BASE_URL = 'http://localhost:28765'


class LLMClient:
    """ReadMate LLM 서버 HTTP 클라이언트."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 120.0) -> None:
        """
        Args:
            base_url: LLM 서버 기본 URL
            timeout: 요청 타임아웃 (초)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def health(self) -> bool:
        """서버 상태를 확인한다."""
        try:
            resp = requests.get(f'{self.base_url}/health', timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def summarize(self, text: str) -> LLMResponse:
        """
        텍스트 요약을 요청한다.

        Args:
            text: 요약할 텍스트

        Returns:
            LLMResponse: 요약 결과

        Raises:
            requests.HTTPError: 서버 오류 시
        """
        resp = requests.post(
            f'{self.base_url}/api/summarize',
            json={'text': text},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return LLMResponse.model_validate(resp.json())

    def qa(self, text: str, question: str) -> LLMResponse:
        """
        질의응답을 요청한다.

        Args:
            text: 참고 텍스트
            question: 사용자 질문

        Returns:
            LLMResponse: 질의응답 결과

        Raises:
            requests.HTTPError: 서버 오류 시
        """
        resp = requests.post(
            f'{self.base_url}/api/qa',
            json={'text': text, 'question': question},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return LLMResponse.model_validate(resp.json())

    def chat(self, messages: list[dict]) -> list[WSResponse]:
        """
        WebSocket으로 다중 메시지를 전송하고 응답을 반환한다.

        Args:
            messages: WSRequest 형식의 dict 리스트
                      [{"task": "summarize"|"qa", "text": "...", "question": "..."}]

        Returns:
            list[WSResponse]: 각 메시지에 대한 응답 리스트
        """
        return asyncio.run(self._chat_async(messages))

    async def _chat_async(self, messages: list[dict]) -> list[WSResponse]:
        ws_url = self.base_url.replace('http://', 'ws://').replace('https://', 'wss://')
        responses: list[WSResponse] = []
        async with websockets.connect(f'{ws_url}/ws/chat') as ws:
            for msg in messages:
                await ws.send(json.dumps(msg))
                raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                responses.append(WSResponse.model_validate(json.loads(raw)))
        return responses

    def session(self, text: str) -> ChatSession:
        """텍스트를 기반으로 ChatSession을 생성한다."""
        return ChatSession(client=self, text=text)


class ChatSession:
    """
    단일 텍스트에 대한 요약 → 반복 질의응답 세션.

    사용 예:
        with client.session(text) as sess:
            print(sess.summary.summary)
            resp = sess.ask("질문")
    """

    def __init__(self, client: LLMClient, text: str) -> None:
        self._client = client
        self._text = text
        self.summary: LLMResponse | None = None
        self._ws_url = client.base_url.replace('http://', 'ws://').replace('https://', 'wss://')
        self._timeout = client.timeout

    def start(self) -> ChatSession:
        """요약을 수행하고 WebSocket 연결을 연다."""
        # 1~2. summarize API 호출 → 요약 수신
        self.summary = self._client.summarize(self._text)
        # 세션 전체에서 재사용할 단일 이벤트 루프 생성
        self._loop = asyncio.new_event_loop()
        self._ws = self._loop.run_until_complete(
            websockets.connect(f'{self._ws_url}/ws/chat')
        )
        return self

    def ask(self, question: str) -> WSResponse:
        """
        질문을 서버에 전송하고 응답을 반환한다.

        Args:
            question: 사용자 질문

        Returns:
            WSResponse: 서버 응답
        """
        return self._loop.run_until_complete(self._ask_async(question))

    async def _ask_async(self, question: str) -> WSResponse:
        payload = json.dumps({'task': 'qa', 'text': self._text, 'question': question})
        await self._ws.send(payload)
        raw = await asyncio.wait_for(self._ws.recv(), timeout=self._timeout)
        return WSResponse.model_validate(json.loads(raw))

    def close(self) -> None:
        """WebSocket 연결을 닫고 이벤트 루프를 정리한다."""
        self._loop.run_until_complete(self._ws.close())
        self._loop.close()

    def __enter__(self) -> ChatSession:
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.close()
