"""
ReadMate 챗봇 인터랙티브 테스트.
텍스트를 요약한 뒤 WebSocket으로 반복 질의응답을 수행한다.

흐름:
    1. summarize API 호출 → 요약 수신
    2. 질문 대기
    3. 질문 → 서버 전송 → 응답 수신
    4. 다음 질문 대기 → 있으면 3 반복 → 없으면 종료

실행:
    uv run python tests/test_chatbot.py
    uv run python tests/test_chatbot.py --url http://localhost:28765
"""

from __future__ import annotations

import argparse

from api.client import DEFAULT_BASE_URL, LLMClient

SAMPLE_TEXT = (
    '인공지능(AI)은 컴퓨터 시스템이 인간의 지능적 행동을 모방하도록 설계된 기술이다. '
    '머신러닝과 딥러닝은 AI의 핵심 분야로, 데이터를 통해 스스로 학습하고 성능을 향상시킨다. '
    '자연어 처리(NLP)는 컴퓨터가 인간의 언어를 이해하고 생성할 수 있게 해주며, '
    'GPT와 같은 대형 언어 모델이 대표적이다. '
    'AI는 의료, 금융, 교육, 제조 등 다양한 산업에 혁신을 가져오고 있으며, '
    '동시에 윤리적 문제와 일자리 대체에 대한 우려도 커지고 있다.'
)


def main() -> None:
    parser = argparse.ArgumentParser(description='ReadMate 챗봇 테스트')
    parser.add_argument('--url', default=DEFAULT_BASE_URL, help=f'서버 URL (기본: {DEFAULT_BASE_URL})')
    args = parser.parse_args()

    client = LLMClient(base_url=args.url)

    print('\n🚀 ReadMate 챗봇 시작')
    print(f'   서버: {args.url}')

    if not client.health():
        print(f'\n❌ 서버에 연결할 수 없습니다: {args.url}')
        print('   uv run uvicorn backend.main:app --port 28765 으로 서버를 먼저 실행하세요.')
        return

    # 1~2. 요약 수행 후 세션 시작
    print('\n📄 텍스트 요약 중...')
    with client.session(SAMPLE_TEXT) as sess:
        summary = sess.summary
        print('\n📝 요약')
        print(f'   {summary.summary}')
        print('\n   핵심 포인트')
        for i, kp in enumerate(summary.key_points, 1):
            print(f'   {i}. {kp}')
        print(f'\n   엔진: {summary.engine}')

        # 3~8. 반복 질의응답
        print('\n💬 질문을 입력하세요. (종료: 빈 입력)')
        print('─' * 55)

        while True:
            try:
                question = input('\n> ').strip()
            except (EOFError, KeyboardInterrupt):
                break

            # 8. 빈 입력 → 종료
            if not question:
                break

            # 4~5. 질문 전송 → 응답 수신
            resp = sess.ask(question)

            if resp.error:
                print(f'❌ 오류: {resp.error}')
                continue

            answer = resp.result.qa_answer if resp.result else None
            print(f'\n💡 {answer or "(응답 없음)"}')

    print('\n세션 종료.')


if __name__ == '__main__':
    main()
