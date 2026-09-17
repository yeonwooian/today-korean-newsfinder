import os
import sys
import argparse
from pathlib import Path

# Windows 콘솔 cp949 인코딩 충돌 방지
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from scraper import scrape_naver_news
from ai_planner import plan_cardnews_and_caption
from renderer import render_cardnews
from telegram_sender import send_cardnews_report


def cleanup_output_dir(output_dir: str | Path) -> int:
    """
    이전에 생성된 카드뉴스 이미지(card_*.png) 및 캡션 텍스트 파일(instagram_caption.txt)을 정리하여
    클라우드 디스크 누적을 방지하고 이전 작업과의 혼선을 차단합니다.
    """
    out_path = Path(output_dir)
    if not out_path.exists():
        out_path.mkdir(parents=True, exist_ok=True)
        return 0

    cleaned_count = 0
    for file_path in out_path.iterdir():
        if file_path.is_file():
            # 카드뉴스 이미지 및 캡션 파일 타겟 정리
            if file_path.name.startswith("card_") or "caption" in file_path.name.lower() or file_path.name.startswith("test_"):
                try:
                    file_path.unlink()
                    cleaned_count += 1
                except Exception as e:
                    print(f"  [경고] 이전 파일 삭제 실패 ({file_path.name}): {e}")
    if cleaned_count > 0:
        print(f"  [OK] 이전 결과물 {cleaned_count}개 파일 정리 완료.")
    return cleaned_count


def run_pipeline(
    url: str,
    output_dir: str = "output",
    send_telegram: bool = False,
    progress_callback = None,
) -> dict:
    """
    네이버 뉴스 URL을 받아 카드뉴스 이미지 렌더링 및 인스타 캡션을 자동 생성합니다.
    (선택 시 텔레그램으로 자동 송신)
    """
    print("\n" + "=" * 60)
    print(" [오늘도국어학원] 인스타그램 카드뉴스 자동생성 파이프라인")
    print("=" * 60)

    # 0. 이전 결과물 정리 (클라우드 용량 누적 방지)
    if progress_callback:
        progress_callback("이전 생성 결과물 파일 정리 중...", 10)
    print(f"\n[0단계] 이전 결과물 디렉터리 정리: {output_dir}")
    cleanup_output_dir(output_dir)

    # 1. 기사 스크래핑
    if progress_callback:
        progress_callback("기사 본문 스크래핑 중...", 20)
    print(f"\n[1단계] 기사 스크래핑 진행 중...")
    print(f"  - URL: {url}")
    article = scrape_naver_news(url)
    print(f"  [OK] 기사 수집 완료: '{article['title']}' (본문 {len(article['content'])}자)")

    # 2. Gemini AI 기획 및 캡션 생성
    if progress_callback:
        progress_callback("Gemini AI 카드뉴스 기획 및 캡션 생성 중...", 50)
    print(f"\n[2단계] Gemini AI 기획 및 인스타 캡션 동시 생성 중...")
    plan_result = plan_cardnews_and_caption(article["title"], article["content"])
    total_pages = plan_result.get("total_pages", len(plan_result.get("cards", [])))
    print(f"  [OK] AI 기획 완료: 총 {total_pages}장 구성 결정")
    for card in plan_result["cards"]:
        print(f"    - Card {card['card_number']} [{card['layout_type']}]: {card['title']}")

    # 3. 4:5 고화질 이미지 렌더링 (Playwright)
    if progress_callback:
        progress_callback("Playwright 1080×1350 고해상도 이미지 렌더링 중...", 80)
    print(f"\n[3단계] Playwright 고해상도(1080×1350) 이미지 렌더링 중...")
    images = render_cardnews(plan_result, output_dir=output_dir)

    # 4. 인스타그램 피드 캡션 파일 저장
    out_dir_path = Path(output_dir)
    caption_file = out_dir_path / "instagram_caption.txt"
    caption_content = plan_result.get("instagram_caption", "")
    with open(caption_file, "w", encoding="utf-8") as f:
        f.write(caption_content)
    print(f"\n[4단계] 인스타그램 캡션 저장 완료 -> {caption_file}")

    # 5. 텔레그램 송신 (옵션)
    telegram_res = None
    if send_telegram:
        if progress_callback:
            progress_callback("텔레그램 채널로 카드뉴스 및 캡션 전송 중...", 95)
        print(f"\n[5단계] 텔레그램 채널로 결과물 발송 중...")
        try:
            telegram_res = send_cardnews_report(
                images=images,
                caption_text=caption_content,
                article_title=article["title"],
            )
            print("  [OK] 텔레그램 전송 성공!")
        except Exception as te:
            print(f"  [경고] 텔레그램 전송 실패: {te}")
            telegram_res = {"success": False, "error": str(te)}

    print("\n" + "=" * 60)
    print(f" [V] 전체 작업 성공! 총 {len(images)}장의 카드뉴스가 생성되었습니다.")
    print(f" [*] 결과물 위치: {out_dir_path.resolve()}")
    print("=" * 60)

    return {
        "article": article,
        "plan": plan_result,
        "images": images,
        "caption": caption_content,
        "caption_file": str(caption_file),
        "telegram_result": telegram_res,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="오늘도국어학원 인스타 카드뉴스 자동생성기")
    parser.add_argument("url", nargs="?", help="네이버 뉴스 URL (n.news.naver.com...)")
    parser.add_argument("--output", "-o", default="output", help="출력 디렉터리 (기본값: output)")
    parser.add_argument("--telegram", "-t", action="store_true", help="텔레그램 채널로 자동 전송")

    args = parser.parse_args()

    target_url = args.url
    if not target_url:
        print("입력된 URL이 없어 콘솔에서 입력을 받습니다.")
        target_url = input("네이버 뉴스 기사 URL을 입력하세요: ").strip()

    if not target_url:
        print("[!] URL이 입력되지 않아 프로그램을 종료합니다.")
        sys.exit(1)

    try:
        run_pipeline(target_url, output_dir=args.output, send_telegram=args.telegram)
    except Exception as e:
        print(f"\n[!] 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
