"""
telegram_bot.py
---------------
오늘도국어학원 텔레그램 모듈.
* 안내: 기존 메시지 수신(Polling) 기능은 완전 비활성화되었습니다.
* 본 모듈은 텔레그램을 오직 '결과물 및 인스타 캡션 송신용'으로만 동작하도록 지원합니다.
"""

import sys
from telegram_sender import send_cardnews_report

if __name__ == "__main__":
    print("=" * 60)
    print(" [안내] 텔레그램 메시지 수신(Polling) 기능이 비활성화되었습니다.")
    print(" 텔레그램은 웹 대시보드(app.py)에서 카드뉴스 생성 완료 시")
    print(" 결과물과 인스타 캡션을 전송하는 송신 전용(Outbound)으로 동작합니다.")
    print("=" * 60)
