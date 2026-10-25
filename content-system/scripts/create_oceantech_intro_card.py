import os
import shutil
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT_PATH = "C:/Windows/Fonts/malgunbd.ttf"
FONT_REGULAR_PATH = "C:/Windows/Fonts/malgun.ttf"

def get_font(size, bold=True):
    path = FONT_PATH if bold else FONT_REGULAR_PATH
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def create_oceantech_intro_card():
    src_base = r"C:\Users\Choijay\.gemini\antigravity-ide\brain\5ce47e1b-1367-4c9f-98c1-ec8a7c1f2880\oceantech_intro_bg_1790643828451.jpg"
    img = Image.open(src_base).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    # 1. Top Header Banner (Fully Opaque Navy)
    draw.rounded_rectangle([w*0.025, 20, w*0.975, 126], radius=14, fill=(15, 23, 42), outline=(56, 189, 248), width=3)
    
    font_main_title = get_font(int(h * 0.044), bold=True)
    font_sub_title = get_font(int(h * 0.023), bold=False)
    draw.text((w/2, 54), "(주)오우션테크놀러지 ｜ 로지텍 화상회의(VC) 공식 수입 총판", font=font_main_title, fill=(255, 255, 255), anchor="mm")
    draw.text((w/2, 95), "서울시 강남구 삼성동 소재 · 공식 B2B 기술 파트너 · 기업 전문 엔지니어링 솔루션", font=font_sub_title, fill=(186, 230, 253), anchor="mm")

    # 2. Left Service Card (B2B Supply & Demo Rental)
    box_left = [w*0.025, h*0.19, w*0.485, h*0.68]
    draw.rounded_rectangle(box_left, radius=14, fill=(248, 250, 252), outline=(2, 132, 199), width=3)
    draw.rounded_rectangle([box_left[0]+8, box_left[1]+8, box_left[2]-8, box_left[1]+56], radius=8, fill=(2, 132, 199))
    
    font_box_header = get_font(int(h * 0.026), bold=True)
    font_item_title = get_font(int(h * 0.024), bold=True)
    font_item_desc = get_font(int(h * 0.020), bold=False)
    
    draw.text(((box_left[0]+box_left[2])/2, box_left[1]+32), "[공식 지원] 기업 납품 & 무상 데모 대여", font=font_box_header, fill=(255, 255, 255), anchor="mm")
    
    left_items = [
        ("1. 로지텍 정품 기업 대량 납품", "공식 수입 총판 정품 보증 및 B2B 맞춤 견적 지원"),
        ("2. 데모 장비 무상 대여 프로그램", "도입 전 고객사 회의실에서 장비를 직접 테스트"),
        ("3. 삼성동 본사 상시 쇼룸 운영", "Rally Bar, MeetUp 2, Tap 등 전 라인업 시연")
    ]
    y_start = box_left[1] + 80
    for t, d in left_items:
        draw.text((box_left[0]+20, y_start), t, font=font_item_title, fill=(3, 105, 161))
        draw.text((box_left[0]+20, y_start+28), d, font=font_item_desc, fill=(71, 85, 105))
        y_start += 82

    # 3. Right Service Card (Engineering & Technical Support)
    box_right = [w*0.515, h*0.19, w*0.975, h*0.68]
    draw.rounded_rectangle(box_right, radius=14, fill=(248, 250, 252), outline=(15, 23, 42), width=3)
    draw.rounded_rectangle([box_right[0]+8, box_right[1]+8, box_right[2]-8, box_right[1]+56], radius=8, fill=(15, 23, 42))
    
    draw.text(((box_right[0]+box_right[2])/2, box_right[1]+32), "[전문 엔지니어] 화각 설계 & 현장 기술 지원", font=font_box_header, fill=(255, 255, 255), anchor="mm")
    
    right_items = [
        ("1. 회의실 공간 맞춤 화각 실측", "테이블 거리 및 인원수 기준 최적 카메라 화각 설계"),
        ("2. Zoom Rooms / Teams 구축", "공식 인증 화상회의 플랫폼 완벽 연동 및 설치 시공"),
        ("3. 신속한 국내 공식 사후 지원", "전문 테크니컬 엔지니어의 상시 기술 지원 및 유지보수")
    ]
    y_start = box_right[1] + 80
    for t, d in right_items:
        draw.text((box_right[0]+20, y_start), t, font=font_item_title, fill=(15, 23, 42))
        draw.text((box_right[0]+20, y_start+28), d, font=font_item_desc, fill=(71, 85, 105))
        y_start += 82

    # 4. Bottom Contact Banner (Fully Opaque)
    draw.rounded_rectangle([w*0.04, h*0.87, w*0.96, h*0.965], radius=12, fill=(15, 23, 42), outline=(56, 189, 248), width=2)
    font_footer = get_font(int(h * 0.024), bold=True)
    draw.text((w/2, h*0.918), "[문의] 기업 대량 납품 & 데모 장비 무상 대여 ｜ 서울 삼성동 본사 쇼룸 방문 예약 가능", font=font_footer, fill=(255, 255, 255), anchor="mm")

    out_file = "company_oceantech_intro.jpg"
    target_dirs = [
        os.path.join(BASE_DIR, "content-system", "05_publish", "assets"),
        os.path.join(BASE_DIR, "static", "assets", "images"),
        os.path.join(BASE_DIR, "logi-blog-app", "public", "assets", "images")
    ]
    for d in target_dirs:
        os.makedirs(d, exist_ok=True)
        dest = os.path.join(d, out_file)
        img.save(dest, quality=95)
        print("Saved to", dest)

if __name__ == "__main__":
    create_oceantech_intro_card()
