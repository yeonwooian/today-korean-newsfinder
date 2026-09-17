"""
telegram_sender.py
------------------
텔레그램 송신 전용 모듈 (Outbound Only).
수신(Polling) 없이, 생성 완료된 카드뉴스 이미지 묶음과 인스타 피드 캡션을
지정된 텔레그램 그룹/채널(오늘도_인스타운영)로 즉각 전송합니다.
"""

from __future__ import annotations

import os
import json
import logging
import requests
from pathlib import Path
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def send_cardnews_report(
    images: list[str | Path],
    caption_text: str,
    article_title: str = "",
    chat_id: str | None = None,
    bot_token: str | None = None,
) -> dict:
    """
    생성된 카드뉴스 이미지들과 인스타그램 캡션을 텔레그램으로 송신합니다.

    1. 카드뉴스 이미지들을 텔레그램 앨범(sendMediaGroup)으로 전송
    2. 스마트폰에서 손쉽게 복사할 수 있도록 인스타 피드 캡션을 단독 메시지로 전송
    """
    token = bot_token or TELEGRAM_BOT_TOKEN
    target_chat = chat_id or TELEGRAM_CHAT_ID

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
    if not target_chat:
        raise ValueError("TELEGRAM_CHAT_ID가 설정되지 않았습니다.")

    base_url = f"https://api.telegram.org/bot{token}"
    valid_images = [Path(p) for p in images if Path(p).exists()]

    if not valid_images:
        raise FileNotFoundError("전송할 카드뉴스 이미지 파일이 존재하지 않습니다.")

    # 1. 미디어 그룹 (사진 앨범) 전송
    media_url = f"{base_url}/sendMediaGroup"
    files = {}
    media = []

    # 텔레그램 앨범은 최대 10장까지 지원
    target_images = valid_images[:10]

    opened_files = []
    try:
        for idx, img_path in enumerate(target_images):
            field_name = f"photo_{idx}"
            f = open(img_path, "rb")
            opened_files.append(f)
            files[field_name] = (img_path.name, f, "image/png")

            item = {
                "type": "photo",
                "media": f"attach://{field_name}",
            }
            if idx == 0:
                lead_title = article_title or "오늘도국어 인스타 카드뉴스"
                item["caption"] = f"📌 {lead_title}\n(자세한 피드 본문 캡션은 아래 메시지를 복사하세요)"

            media.append(item)

        data = {
            "chat_id": str(target_chat),
            "media": json.dumps(media),
        }

        resp = requests.post(media_url, data=data, files=files, timeout=60)
        resp_json = resp.json()

        if not resp_json.get("ok"):
            logger.error(f"텔레그램 미디어 그룹 전송 실패: {resp_json}")
            return {
                "success": False,
                "error": f"미디어 전송 오류: {resp_json.get('description', '알 수 없는 오류')}"
            }
    finally:
        for f in opened_files:
            try:
                f.close()
            except Exception:
                pass

    # 2. 인스타 피드 캡션 텍스트 단독 전송 (모바일에서 한 번에 탭하여 복사 가능)
    if caption_text and caption_text.strip():
        msg_url = f"{base_url}/sendMessage"
        # 텔레그램 단일 메시지 한도 4096자
        cleaned_caption = caption_text.strip()[:4000]
        text_data = {
            "chat_id": str(target_chat),
            "text": cleaned_caption,
        }
        try:
            c_resp = requests.post(msg_url, json=text_data, timeout=20)
            if not c_resp.json().get("ok"):
                logger.warning(f"캡션 전송 오류: {c_resp.text}")
        except Exception as ce:
            logger.warning(f"캡션 전송 중 예외: {ce}")

    return {
        "success": True,
        "chat_id": target_chat,
        "total_images": len(target_images),
    }


if __name__ == "__main__":
    import sys
    print("[*] 텔레그램 송신 전용 모듈 테스트")
    print(f"  - Target Chat ID: {TELEGRAM_CHAT_ID}")
    # 간단한 텍스트 핑 테스트
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": "🔔 [오늘도국어] 텔레그램 송신 모듈 연결 확인 완료."},
        timeout=10,
    )
    print("  - Response:", r.json())
