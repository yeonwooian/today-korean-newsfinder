import os
import sys
import subprocess
import re
import random
import pathlib
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader
import base64

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    print("[*] 클라우드 환경 Playwright 라이브러리 자동 설치 중...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright>=1.40.0"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        from playwright.sync_api import sync_playwright
    except Exception as ie:
        raise ModuleNotFoundError(
            f"Playwright 설치 실패: {ie}. GitHub requirements.txt에 'playwright>=1.40.0'이 포함되어 있는지 확인해주세요."
        )

def get_image_data_uri(file_path: pathlib.Path) -> str:
    """로컬 이미지 파일을 Playwright가 안전하게 렌더링할 수 있도록 base64 data URI로 변환"""
    if not file_path.exists():
        return ""
    suffix = file_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    with open(file_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{data}"

_FONT_CACHE: Dict[str, str] = {}

def get_font_data_uri(file_path: pathlib.Path) -> str:
    """로컬 폰트 파일을 CSS @font-face 용 base64 data URI로 변환"""
    path_str = str(file_path.resolve())
    if path_str in _FONT_CACHE:
        return _FONT_CACHE[path_str]
    if not file_path.exists():
        return ""
    suffix = file_path.suffix.lower()
    if suffix == ".woff2":
        mime = "font/woff2"
    elif suffix == ".woff":
        mime = "font/woff"
    elif suffix == ".otf":
        mime = "font/otf"
    else:
        mime = "font/truetype"
    with open(file_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    uri = f"data:{mime};charset=utf-8;base64,{data}"
    _FONT_CACHE[path_str] = uri
    return uri

CHALK_STICK_COLORS = [
    "#FFB38A",  # 피치
    "#A2D6E6",  # 스카이블루
    "#FDE887",  # 레몬 옐로우
    "#FFAAA6",  # 소프트 코랄핑크
    "#A8E6CF",  # 민트 그린
    "#D0BFFF",  # 라벤더 바이올렛
    "#FFBE76",  # 탠저린 오렌지
    "#F0F2F5",  # 분필 화이트
    "#FFD166",  # 골든 옐로우
    "#74C0FC",  # 파스텔 블루
    "#FFCAD4",  # 파우더 핑크
]

DOODLE_STAR_COLORS = [
    "#FDE887", "#A2D6E6", "#FFAAA6", "#A8E6CF", "#D0BFFF", "#FFBE76", "#FFD166"
]

DOODLE_ELLIPSE_COLORS = [
    "#A2D6E6", "#FDE887", "#FFAAA6", "#A8E6CF", "#D0BFFF", "#FFB38A"
]

def format_magazine_title(title: str, style: str = "magazine_a") -> str:
    """매거진 커버용 헤드라인 자동 하이라이트 포맷터"""
    if not title:
        return ""
    title = title.replace("\\n", "\n")
    if "<span" in title or "<br" in title:
        return title.replace("\n", "<br>")
    
    lines = [line.strip() for line in title.split("\n") if line.strip()]
    if len(lines) >= 2:
        if style == "magazine_a":
            res = []
            for i, l in enumerate(lines):
                if i == 0:
                    res.append(f'<span class="title-white">{l}</span>')
                elif i == 1:
                    res.append(f'<span class="title-highlight">{l}</span>')
                else:
                    res.append(f'<span class="title-white">{l}</span>')
            return "".join(res)
        else: # magazine_b
            res = []
            for i, l in enumerate(lines):
                if i == 0:
                    res.append(l)
                elif i == 1:
                    res.append(f'<span class="focus-word">{l}</span>')
                elif i == 2:
                    res.append(f'<span class="accent-cyan">{l}</span>')
                else:
                    res.append(l)
            return "<br>".join(res)

    if "?" in title:
        parts = title.split("?", 1)
        part1 = parts[0].strip() + "?"
        part2 = parts[1].strip()
        if style == "magazine_a":
            return f'<span class="title-highlight">{part1}</span><span class="title-white">{part2}</span>'
        else:
            return f'<span class="focus-word">{part1}</span><br><span class="accent-cyan">{part2}</span>'
    
    return title

def render_cardnews(
    plan_data: Dict[str, Any], 
    output_dir: str = "output",
    cover_bg_filename: Optional[str] = None,
    cover_style: Optional[str] = None,
    body_style: str = "dark_signature"
) -> List[str]:
    """
    AI 기획 데이터(JSON)를 기반으로 1080x1350 고화질 카드뉴스 PNG 이미지들을 렌더링합니다.
    
    :param plan_data: ai_planner에서 생성된 딕셔너리 (cards, total_pages 포함)
    :param output_dir: 결과 이미지를 저장할 디렉터리 경로
    :param cover_bg_filename: 특정 표지 배경 이미지 지정 (예: '02.png', None이면 랜덤)
    :param cover_style: 표지 스타일 ('classic', 'magazine_a', 'magazine_b', None이면 무작위 추첨)
    :param body_style: 본문 레이아웃 스타일 ('dark_signature' 또는 'blackboard')
    :return: 생성된 이미지 파일 경로 리스트
    """
    base_dir = pathlib.Path(__file__).parent.resolve()
    templates_dir = base_dir / "templates"
    bg_dir = base_dir / "background"
    out_path_dir = pathlib.Path(output_dir).resolve()
    out_path_dir.mkdir(parents=True, exist_ok=True)
    # 이전 카드뉴스 잔여 이미지 삭제 (새로 렌더링할 장수 차이로 인한 누적 및 용량 낭비 방지)
    for old_card in out_path_dir.glob("card_*.png"):
        try:
            old_card.unlink()
        except Exception:
            pass
    logo_white_uri = get_image_data_uri(bg_dir / "logo_white.png")
    logo_black_uri = get_image_data_uri(bg_dir / "logo_black.png")
    bg_lee_uri = get_image_data_uri(bg_dir / "오늘도국어_이T.jpg")
    bg_cho_uri = get_image_data_uri(bg_dir / "오늘도국어_조T.jpg")
    font_aggro_uri = get_font_data_uri(base_dir / "font" / "SB 어그로 B.ttf")
    font_pretendard_regular_uri = get_font_data_uri(base_dir / "font" / "Pretendard-Regular.woff2")
    font_pretendard_medium_uri = get_font_data_uri(base_dir / "font" / "Pretendard-Medium.woff2")
    font_pretendard_bold_uri = get_font_data_uri(base_dir / "font" / "Pretendard-Bold.woff2")
    newspaper_transparent_uri = get_image_data_uri(bg_dir / "newspaper_transparent.png")
    news_photo_sample_uri = get_image_data_uri(bg_dir / "news_photo_sample.jpg")

    # 01.png ~ 99.png 중 배경 이미지 선택
    cover_bg_candidates = [
        f for f in bg_dir.glob("*.png")
        if re.match(r"^\d{2}\.png$", f.name) and 1 <= int(f.stem) <= 99
    ]
    if cover_bg_filename and (bg_dir / cover_bg_filename).exists():
        chosen_cover_bg = bg_dir / cover_bg_filename
        cover_bg_uri = get_image_data_uri(chosen_cover_bg)
        print(f"[*] 표지(Card 1) 지정 배경 이미지 적용: {chosen_cover_bg.name}")
    elif cover_bg_candidates:
        chosen_cover_bg = random.choice(cover_bg_candidates)
        cover_bg_uri = get_image_data_uri(chosen_cover_bg)
        print(f"[*] 표지(Card 1) 랜덤 배경 이미지 적용: {chosen_cover_bg.name}")
    else:
        cover_bg_uri = ""

    # Jinja2 템플릿 환경 설정
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
    cover_templates = {
        "classic": env.get_template("cover_template.html"),
        "magazine_a": env.get_template("cover_magazine_a.html"),
        "magazine_b": env.get_template("cover_magazine_b.html")
    }
    card_tmpl_dark = env.get_template("card_template.html")
    card_tmpl_blackboard = env.get_template("card_blackboard.html") if (templates_dir / "card_blackboard.html").exists() else card_tmpl_dark
    card_tmpl_newspaper = env.get_template("card_newspaper.html") if (templates_dir / "card_newspaper.html").exists() else card_tmpl_dark

    # 3가지 표지 스타일 중 무작위 선택 (또는 명시적 지정)
    chosen_cover_style = cover_style or random.choice(["classic", "magazine_a", "magazine_b"])
    chosen_cover_tmpl = cover_templates.get(chosen_cover_style, cover_templates["classic"])
    print(f"[*] 표지(Card 1) 디자인 스타일 적용: '{chosen_cover_style}' | 본문 스타일: '{body_style}'")

    import datetime
    current_date_str = datetime.datetime.now().strftime("%Y.%m.%d BRIEFING")

    total_pages = plan_data.get("total_pages", len(plan_data.get("cards", [])))
    cards = plan_data.get("cards", [])
    generated_images = []

    print(f"[*] 총 {len(cards)}장의 카드뉴스 렌더링 시작 (해상도: 1080×1350)...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
        except Exception as launch_err:
            # Streamlit Cloud 또는 리눅스 환경에서 Chromium 바이너리 미설치 시 자동 설치 시도
            print(f"[*] Chromium 최초 실행 오류 감지, 설치 시도 중: {launch_err}")
            import subprocess
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
        # 1080x1350 고정 뷰포트 설정
        context = browser.new_context(
            viewport={"width": 1080, "height": 1350},
            device_scale_factor=1
        )
        page = context.new_page()

        for card in cards:
            c_num = card["card_number"]
            is_cover = (c_num == 1 and card.get("layout_type") == "cover") or (card.get("layout_type") == "cover")

            # Jinja2 dict.items 충돌 방지 및 안전한 items 리스트 보장
            card_copy = dict(card)
            raw_items = card_copy.get("items")
            if not isinstance(raw_items, list):
                if card_copy.get("desc"):
                    card_copy["items"] = [{"label": card_copy.get("subtitle") or "핵심 분석", "detail": card_copy["desc"]}]
                else:
                    card_copy["items"] = [{"label": card_copy.get("subtitle") or "핵심 요약", "detail": ""}]
            elif len(raw_items) == 0:
                card_copy["items"] = [{"label": card_copy.get("subtitle") or "핵심 요약", "detail": card_copy.get("desc") or ""}]

            if is_cover:
                if chosen_cover_style in ["magazine_a", "magazine_b"]:
                    card_copy["title_html"] = format_magazine_title(card_copy.get("title", ""), style=chosen_cover_style)

                html_content = chosen_cover_tmpl.render(
                    card=card_copy,
                    total_pages=total_pages,
                    logo_path=logo_white_uri,
                    bg_image_path=cover_bg_uri,
                    current_date_str=current_date_str,
                    font_aggro_uri=font_aggro_uri,
                    font_pretendard_regular_uri=font_pretendard_regular_uri,
                    font_pretendard_medium_uri=font_pretendard_medium_uri,
                    font_pretendard_bold_uri=font_pretendard_bold_uri
                )
            else:
                if body_style == "blackboard":
                    left_count = random.choice([2, 3])
                    right_count = random.choice([2, 3])
                    total_needed = left_count + right_count
                    sample_colors = random.sample(CHALK_STICK_COLORS, min(total_needed, len(CHALK_STICK_COLORS)))
                    if len(sample_colors) < total_needed:
                        sample_colors += [random.choice(CHALK_STICK_COLORS) for _ in range(total_needed - len(sample_colors))]
                    random.shuffle(sample_colors)
                    left_chalks = [
                        {
                            "color": sample_colors[i],
                            "width": random.randint(48, 85),
                            "height": random.randint(16, 20),
                            "radius": f"{random.randint(3, 5)}px {random.randint(3, 5)}px {random.randint(1, 3)}px {random.randint(1, 3)}px"
                        }
                        for i in range(left_count)
                    ]
                    right_chalks = [
                        {
                            "color": sample_colors[left_count + i],
                            "width": random.randint(45, 90),
                            "height": random.randint(16, 20),
                            "radius": f"{random.randint(3, 5)}px {random.randint(3, 5)}px {random.randint(1, 3)}px {random.randint(1, 3)}px"
                        }
                        for i in range(right_count)
                    ]
                    chalk_tray = {"left": left_chalks, "right": right_chalks}
                    doodle_colors = {
                        "ellipse": random.choice(DOODLE_ELLIPSE_COLORS),
                        "star_left": random.choice(DOODLE_STAR_COLORS),
                        "star_right": random.choice(DOODLE_STAR_COLORS),
                        "underline": random.choice(["rgba(255, 255, 255, 0.75)", "#FDE887", "#A2D6E6", "#FFAAA6", "#A8E6CF", "#FFBE76"]),
                    }
                    html_content = card_tmpl_blackboard.render(
                        card=card_copy,
                        total_pages=total_pages,
                        logo_path=logo_white_uri,
                        logo_black_path=logo_black_uri,
                        font_aggro_uri=font_aggro_uri,
                        font_pretendard_regular_uri=font_pretendard_regular_uri,
                        font_pretendard_medium_uri=font_pretendard_medium_uri,
                        font_pretendard_bold_uri=font_pretendard_bold_uri,
                        chalk_tray=chalk_tray,
                        doodle_colors=doodle_colors
                    )
                elif body_style == "newspaper":
                    html_content = card_tmpl_newspaper.render(
                        card=card_copy,
                        total_pages=total_pages,
                        logo_path=logo_white_uri,
                        logo_black_path=logo_black_uri,
                        font_aggro_uri=font_aggro_uri,
                        font_pretendard_regular_uri=font_pretendard_regular_uri,
                        font_pretendard_medium_uri=font_pretendard_medium_uri,
                        font_pretendard_bold_uri=font_pretendard_bold_uri,
                        newspaper_img_uri=newspaper_transparent_uri,
                        photo_img_uri=news_photo_sample_uri
                    )
                else: # dark_signature
                    # 본문 배경은 조T -> 이T 순으로 교대 적용 (Card 2: 조T, Card 3: 이T, Card 4: 조T ...)
                    current_bg = bg_cho_uri if (c_num % 2 == 0) else bg_lee_uri
                    html_content = card_tmpl_dark.render(
                        card=card_copy,
                        total_pages=total_pages,
                        bg_image_path=current_bg,
                        logo_path=logo_white_uri,
                        font_aggro_uri=font_aggro_uri,
                        font_pretendard_regular_uri=font_pretendard_regular_uri,
                        font_pretendard_medium_uri=font_pretendard_medium_uri,
                        font_pretendard_bold_uri=font_pretendard_bold_uri
                    )

            # HTML 주입 및 웹폰트/이미지 로딩 대기
            page.set_content(html_content, wait_until="load")
            try:
                page.evaluate("() => document.fonts.ready")
            except Exception:
                pass
            page.wait_for_timeout(200) # 폰트 렌더링 안정화 200ms
            page.evaluate("if (typeof autoFitAllElements === 'function') autoFitAllElements();")

            output_file = out_path_dir / f"card_{c_num}.png"
            page.screenshot(path=str(output_file), type="png")
            generated_images.append(str(output_file))
            print(f"  [OK] Card {c_num} 렌더링 완료 -> {output_file.name}")

        browser.close()

    print(f"[!] 렌더링 성공: 총 {len(generated_images)}개 파일 생성 완료.")
    return generated_images

if __name__ == "__main__":
    # 렌더링 단독 테스트용 목업 데이터
    sample_plan = {
        "total_pages": 4,
        "cards": [
            {
                "card_number": 1,
                "badge": "2027 수시 긴급 분석",
                "title": "반도체 계약학과 지원자 역대 최고치 경신",
                "subtitle": "삼성전자 · SK하이닉스 연계 5개 대학 총 5,992명 몰려",
                "layout_type": "cover",
                "items": [
                    {"label": "전년 대비 증가율", "value": "+19.4% ▲"},
                    {"label": "최고 경쟁률 학과", "value": "서강대 (66.15 : 1)"}
                ]
            },
            {
                "card_number": 2,
                "badge": "핵심 수치 팩트체크",
                "title": "수시 지원자 수와 경쟁률 동반 급등",
                "subtitle": "취업 보장형 채용조건 계약학과의 독주",
                "layout_type": "stat",
                "items": [
                    {"label": "총 지원자 수", "value": "5,992명", "sub": "+19.4% ▲", "detail": "작년 5,020명 대비 972명 증가", "highlight": "orange", "sub_highlight": "orange"},
                    {"label": "평균 경쟁률", "value": "28.53 : 1", "sub": "급등", "detail": "전년도 23.90 : 1 대비 대폭 상승", "highlight": "orange", "sub_highlight": "blue"}
                ],
                "footer_insight": "상위권 자연계 수험생들의 안정 선호 심리가 크게 작용"
            },
            {
                "card_number": 3,
                "badge": "기업별 대조 분석",
                "title": "SK하이닉스 vs 삼성전자 연계 대학",
                "subtitle": "하이닉스 연계 대학의 지원자 증가세가 두드러져",
                "layout_type": "comparison",
                "items": [
                    {"label": "SK하이닉스 연계", "value": "+27.3% ▲", "detail": "고려대, 서강대, 한양대 총 3,152명 지원", "color": "orange"},
                    {"label": "삼성전자 연계", "value": "+11.7% ▲", "detail": "연세대, 성균관대 총 2,840명 지원", "color": "blue"}
                ],
                "footer_insight": "반도체 업황 개선 기대감과 모집 인원 차이가 반영됨"
            },
            {
                "card_number": 4,
                "badge": "최종 결론 및 변수",
                "title": "의대 정원 확대와 충원 합격 변수",
                "subtitle": "복수합격자 이동에 따른 추가 합격선 주목",
                "layout_type": "conclusion",
                "items": [
                    {"label": "지역의사제 신설 여파", "detail": "최상위권 의대 복수합격자의 연쇄 이동 가능성", "color": "orange"},
                    {"label": "계약학과의 전략적 지원", "detail": "의대 정시 대비 안전판으로 수시 집중 양상", "color": "blue"}
                ],
                "footer_insight": "수시 충원합격 마감 시점까지 실질 등록률 추이를 주시해야 함"
            }
        ]
    }
    # 02.png 표지 렌더링 테스트
    render_cardnews(sample_plan, cover_bg_filename="02.png")
