"""
Logitech AI 단발 테스트 - 서버 모드 없이 직접 질문 후 종료
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ask_logitech_ai import LogitechAI

TEST_QUESTION = "What is RightSight 2 and what are the available view modes for Rally Bar?"

print("=" * 60)
print("Logitech AI 단발 질의 테스트")
print("=" * 60)

bot = LogitechAI(headless=False)  # headless=False로 디버깅 가능하게
try:
    bot.reset_chat()
    response = bot.ask(TEST_QUESTION)
    
    print("\n" + "=" * 60)
    print("=== LOGITECH AI RESPONSE ===")
    print("=" * 60)
    if response:
        print(response[:2000])  # 처음 2000자만 출력
        print(f"\n[총 응답 길이: {len(response)} chars]")
    else:
        print("None - 응답을 받지 못했습니다.")
    print("=" * 60)
finally:
    bot.close()
    print("\n>> 브라우저 종료 완료.")
