import os
import sys
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

def process_concept_huddle_fov():
    src_path = os.path.join(BASE_DIR, "static", "assets", "images", "concept_huddle_fov.jpg")
    if not os.path.exists(src_path):
        print("Source not found:", src_path)
        return
    
    img = Image.open(src_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    
    # 1. Overlay Title Bar at Top
    # Top banner area: y = 20 to 120
    # Create semi-transparent overlay surface
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    ov_draw = ImageDraw.Draw(overlay)
    
    # Header background card
    ov_draw.rounded_rectangle([w*0.04, 30, w*0.96, 125], radius=16, fill=(15, 23, 42, 235), outline=(56, 189, 248, 200), width=2)
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    
    font_main_title = get_font(int(h * 0.046), bold=True)
    font_sub_title = get_font(int(h * 0.024), bold=False)
    
    title_text = "소형 회의실 카메라 화각(FOV) 한계와 120° 초광각 비교"
    sub_text = "일반 데스크톱 웹캠(78°~90°)의 양옆 잘림 한계 vs 120° 초광각 렌즈 공간 커버리지"
    
    # Center text in header
    draw.text((w/2, 60), title_text, font=font_main_title, fill=(255, 255, 255), anchor="mm")
    draw.text((w/2, 102), sub_text, font=font_sub_title, fill=(186, 230, 253), anchor="mm")
    
    # 2. Left Box Overlay: NARROW FOV PROBLEMS
    # Left box: x: w*0.04 to w*0.36, y: h*0.22 to h*0.68
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    ov_draw = ImageDraw.Draw(overlay)
    
    box_left = [w*0.045, h*0.22, w*0.355, h*0.67]
    ov_draw.rounded_rectangle(box_left, radius=14, fill=(255, 241, 242, 245), outline=(225, 29, 72, 220), width=3)
    
    # Header pill for left box
    ov_draw.rounded_rectangle([box_left[0]+12, box_left[1]+12, box_left[2]-12, box_left[1]+56], radius=8, fill=(225, 29, 72, 255))
    
    # Right Box Overlay: 120 ULTRA-WIDE ADVANTAGES
    box_right = [w*0.645, h*0.22, w*0.955, h*0.67]
    ov_draw.rounded_rectangle(box_right, radius=14, fill=(240, 249, 255, 245), outline=(2, 132, 199, 220), width=3)
    
    # Header pill for right box
    ov_draw.rounded_rectangle([box_right[0]+12, box_right[1]+12, box_right[2]-12, box_right[1]+56], radius=8, fill=(2, 132, 199, 255))
    
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    
    font_box_header = get_font(int(h * 0.027), bold=True)
    font_bullets = get_font(int(h * 0.024), bold=True)
    font_bullets_sub = get_font(int(h * 0.020), bold=False)
    
    # Left Box Texts
    draw.text(((box_left[0]+box_left[2])/2, box_left[1]+34), "⚠️ 일반 좁은 화각(78°~90°) 문제점", font=font_box_header, fill=(255, 255, 255), anchor="mm")
    
    left_items = [
        ("1. 양옆 끝자리 인물 잘림", "테이블 좌우 팀원의 얼굴 반쪽만 송출됨"),
        ("2. 1.0m 근접 시 사각지대", "좁은 허들룸 특성상 뒤로 물러설 수 없음"),
        ("3. 억지로 몸을 기울임", "화면에 비치기 위해 허리를 숙여야 함"),
        ("4. 카메라 수동 회전 불편", "발언자마다 리모컨으로 각도를 조절해야 함")
    ]
    
    y_start = box_left[1] + 75
    for title, desc in left_items:
        draw.text((box_left[0]+22, y_start), title, font=font_bullets, fill=(190, 18, 60))
        draw.text((box_left[0]+22, y_start+28), desc, font=font_bullets_sub, fill=(71, 85, 105))
        y_start += 66
        
    # Right Box Texts
    draw.text(((box_right[0]+box_right[2])/2, box_right[1]+34), "✅ 120° 초광각 커버리지 장점", font=font_box_header, fill=(255, 255, 255), anchor="mm")
    
    right_items = [
        ("1. 참석자 전원 한 화면 포착", "120° 광각으로 좌우 사각지대 완전 제거"),
        ("2. 1.0m 근접 거리 완벽 지원", "좁은 테이블에서도 뒤로 물러설 필요 없음"),
        ("3. 자연스러운 회의 자세 유지", "몸을 기울이지 않고 편안하게 발언"),
        ("4. RightSight 2 자동 프레이밍", "인원수에 맞춰 카메라가 스스로 화각 최적화")
    ]
    
    y_start = box_right[1] + 75
    for title, desc in right_items:
        draw.text((box_right[0]+22, y_start), title, font=font_bullets, fill=(3, 105, 161))
        draw.text((box_right[0]+22, y_start+28), desc, font=font_bullets_sub, fill=(71, 85, 105))
        y_start += 66
        
    # Bottom Note Banner
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rounded_rectangle([w*0.2, h*0.88, w*0.8, h*0.96], radius=10, fill=(15, 23, 42, 220))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    font_footer = get_font(int(h * 0.023), bold=True)
    draw.text((w/2, h*0.92), "💡 소형 룸 기준: 참석자 거리 1.0m~4.5m 이내 최적 작동 (출처: 오우션 엔지니어링 분석)", font=font_footer, fill=(255, 255, 255), anchor="mm")
    
    # Save back to RGB JPEG
    final_rgb = img.convert("RGB")
    final_rgb.save(src_path, quality=95)
    print("[SUCCESS] Processed concept_huddle_fov.jpg with Korean text!")

if __name__ == "__main__":
    process_concept_huddle_fov()
