"""
ReadMate LLM 서버 테스트 스크립트.

사전 조건:
    서버 실행: uv run uvicorn backend.main:app --reload --port 8000

사용법:
    # HTTP 요약 테스트
    uv run python scripts/test_llm_server.py --mode http-summarize

    # HTTP 질의응답 테스트
    uv run python scripts/test_llm_server.py --mode http-qa

    # WebSocket 테스트 (대화형)
    uv run python scripts/test_llm_server.py --mode ws

    # 커스텀 서버 주소
    uv run python scripts/test_llm_server.py --mode http-summarize --host localhost --port 8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.request

SAMPLE_TEXT = """
조선시대의 과거제도는 고려시대에 도입된 과거시험 제도를 계승하여 발전시킨 것으로,
문과·무과·잡과로 나뉘었다. 문과는 유교 경전과 문학적 소양을 시험하였고,
무과는 무예와 병법을 평가하였다. 잡과는 의학·법학·외국어 등 실용적 전문 지식을 평가하였다.
과거시험은 3년마다 정기적으로 치러졌으며, 합격자는 관료로 등용되어 국가 행정을 담당하였다.
이 제도는 신분에 관계없이 능력에 따라 관직에 오를 수 있는 기회를 제공했으나,
실질적으로는 양반 계층이 대부분의 합격자를 차지하였다.
"""

SAMPLE_QUESTION = '과거시험은 얼마나 자주 치러졌나요?'


def test_http_summarize(base_url: str) -> None:
    """
    HTTP POST /api/summarize 엔드포인트를 테스트한다.

    Args:
        base_url: 서버 기본 URL (예: http://localhost:8000)
    """
    url = f'{base_url}/api/summarize'
    payload = json.dumps({'text': SAMPLE_TEXT}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={'Content-Type': 'application/json'}, method='POST'
    )
    print(f'[HTTP] POST {url}')
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    _print_result(result)


def test_http_qa(base_url: str) -> None:
    """
    HTTP POST /api/qa 엔드포인트를 테스트한다.

    Args:
        base_url: 서버 기본 URL
    """
    url = f'{base_url}/api/qa'
    payload = json.dumps({'text': SAMPLE_TEXT, 'question': SAMPLE_QUESTION}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={'Content-Type': 'application/json'}, method='POST'
    )
    print(f'[HTTP] POST {url}')
    print(f'[HTTP] question: {SAMPLE_QUESTION}')
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    _print_result(result)


async def test_ws(ws_url: str) -> None:
    """
    WebSocket /ws/chat 엔드포인트를 대화형으로 테스트한다.

    Args:
        ws_url: WebSocket 서버 URL (예: ws://localhost:8000)
    """
    try:
        import websockets
    except ImportError:
        print('[오류] websockets 패키지가 필요합니다: uv add websockets')
        sys.exit(1)

    url = f'{ws_url}/ws/chat'
    print(f'[WS] 연결 중: {url}')
    print('[WS] 메시지 형식: {"task": "summarize"|"qa", "text": "...", "question": "..."}')
    print('[WS] 종료: Ctrl+C 또는 빈 입력\n')

    async with websockets.connect(url) as ws:
        # 자동 샘플 전송
        for task, question in [('summarize', None), ('qa', SAMPLE_QUESTION)]:
            msg: dict = {'task': task, 'text': SAMPLE_TEXT}
            if question:
                msg['question'] = question
            print(f'[WS] 전송 → task={task}')
            await ws.send(json.dumps(msg, ensure_ascii=False))
            raw = await ws.recv()
            resp = json.loads(raw)
            if resp.get('error'):
                print(f'[WS] 오류: {resp["error"]}')
            else:
                _print_result(resp.get('result', {}))
            print()

        # 대화형 입력
        print('[WS] 직접 메시지를 입력하세요 (빈 입력 시 종료):')
        while True:
            try:
                user_input = input('> ').strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input:
                break
            await ws.send(user_input)
            raw = await ws.recv()
            resp = json.loads(raw)
            if resp.get('error'):
                print(f'[오류] {resp["error"]}')
            else:
                _print_result(resp.get('result', {}))


def _print_result(result: dict) -> None:
    """
    LLMResponse 딕셔너리를 보기 좋게 출력한다.

    Args:
        result: LLMResponse 딕셔너리
    """
    print(f'\n엔진: {result.get("engine", "-")}')
    print(f'요약:\n  {result.get("summary", "-")}')
    print('핵심 포인트:')
    for kp in result.get('key_points', []):
        print(f'  • {kp}')
    if result.get('qa_answer'):
        print(f'답변:\n  {result["qa_answer"]}')


def main() -> None:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(description='ReadMate LLM 서버 테스트')
    parser.add_argument(
        '--mode',
        choices=['http-summarize', 'http-qa', 'ws'],
        default='http-summarize',
    )
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()

    base_url = f'http://{args.host}:{args.port}'
    ws_url = f'ws://{args.host}:{args.port}'

    if args.mode == 'http-summarize':
        test_http_summarize(base_url)
    elif args.mode == 'http-qa':
        test_http_qa(base_url)
    elif args.mode == 'ws':
        asyncio.run(test_ws(ws_url))


if __name__ == '__main__':
    main()
