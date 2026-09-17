import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional

# 웹 브라우저 헤더 (봇 차단 방지)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

def clean_text(text: str) -> str:
    """기사 본문 노이즈(이메일, 바이라인, 중복 공백) 정제"""
    # 기자 이메일 주소 제거
    text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "", text)
    # 대괄호/소괄호 안의 기자 정보 및 송고지 제거 (예: [서울=뉴스1] 김기자 =)
    text = re.sub(r"\[.*?\]|\(.*?\)", "", text)
    # 3연속 이상 줄바꿈을 2단 줄바꿈으로 통일
    text = re.sub(r"\n\s*\n", "\n\n", text)
    # 연속된 공백 및 탭 정리
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def scrape_naver_news(url: str) -> Dict[str, Optional[str]]:
    """
    네이버 뉴스 URL(PC, 모바일 모두 지원)에서 제목과 본문을 추출합니다.
    
    :param url: https://n.news.naver.com/... 또는 https://news.naver.com/...
    :return: {"title": 제목, "content": 정제된 본문, "url": URL}
    """
    if "news.naver.com" not in url:
        raise ValueError("네이버 뉴스(news.naver.com) URL만 지원합니다.")

    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 1. 기사 제목 추출
    title_tag = (
        soup.select_one("#title_area span")
        or soup.select_one("#title_area")
        or soup.select_one(".media_end_head_headline")
        or soup.select_one("h2.end_tit")
    )
    title = title_tag.get_text().strip() if title_tag else "제목 없음"

    # 2. 기사 본문 영역 추출
    content_area = (
        soup.select_one("#dic_area")
        or soup.select_one("#newsct_article")
        or soup.select_one("#articeBody")
    )
    if not content_area:
        raise ValueError("기사 본문 영역을 파싱할 수 없습니다.")

    # 3. 불필요 태그 제거 (사진 설명문, 스크립트, 광고, 바이라인)
    for unwanted in content_area.select(".img_desc, em.img_desc, script, style, .byline, iframe"):
        unwanted.decompose()

    # 4. 정제된 텍스트 반환
    raw_content = content_area.get_text(separator="\n")
    cleaned_content = clean_text(raw_content)

    return {
        "title": title,
        "content": cleaned_content,
        "url": url
    }

if __name__ == "__main__":
    sample_url = "https://n.news.naver.com/mnews/article/001/0014923456"
    print(f"[*] 테스트 스크래핑 시도: {sample_url}")
    try:
        data = scrape_naver_news(sample_url)
        print(f"[제목] {data['title']}")
        print(f"[본문 미리보기 (200자)]\n{data['content'][:200]}...")
    except Exception as e:
        print(f"[!] 에러: {e}")
