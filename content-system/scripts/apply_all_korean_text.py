import os
import sys
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

def sync_asset_to_all_folders(file_name, source_img_path):
    target_dirs = [
        os.path.join(BASE_DIR, "content-system", "05_publish", "assets"),
        os.path.join(BASE_DIR, "static", "assets", "images"),
        os.path.join(BASE_DIR, "logi-blog-app", "public", "assets", "images")
    ]
    for d in target_dirs:
        os.makedirs(d, exist_ok=True)
        dest = os.path.join(d, file_name)
        if os.path.abspath(source_img_path) != os.path.abspath(dest):
            shutil.copy2(source_img_path, dest)
    print(f"  -> Synced {file_name} across all static asset folders.")

# -------------------------------------------------------------
# 1. Concept: FOV Comparison (100% Korean, Fully Opaque Overlays)
# -------------------------------------------------------------
def process_concept_huddle_fov():
    src_base = r"C:\Users\Choijay\.gemini\antigravity-ide\brain\5ce47e1b-1367-4c9f-98c1-ec8a7c1f2880\anim_huddle_fov_ppt_1790641150608.jpg"
    img = Image.open(src_base).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)
    
    # 1. Top Header Card (Fully Opaque)
    header_box = [w*0.025, 20, w*0.975, 126]
    draw.rounded_rectangle(header_box, radius=14, fill=(15, 23, 42), outline=(56, 189, 248), width=3)
    
    font_main_title = get_font(int(h * 0.044), bold=True)
    font_sub_title = get_font(int(h * 0.023), bold=False)
    draw.text((w/2, 54), "소형 회의실 카메라 화각(FOV) 한계와 120° 초광각 비교", font=font_main_title, fill=(255, 255, 255), anchor="mm")
    draw.text((w/2, 95), "일반 데스크톱 웹캠(78°~90°)의 양옆 잘림 한계 vs 120° 초광각 렌즈 공간 커버리지", font=font_sub_title, fill=(186, 230, 253), anchor="mm")
    
    # 2. Left Problem Card (Fully Opaque, wider to completely cover English text)
    box_left = [w*0.025, h*0.19, w*0.375, h*0.70]
    draw.rounded_rectangle(box_left, radius=14, fill=(255, 245, 245), outline=(225, 29, 72), width=3)
    # Header pill
    draw.rounded_rectangle([box_left[0]+8, box_left[1]+8, box_left[2]-8, box_left[1]+56], radius=8, fill=(225, 29, 72))
    
    font_box_header = get_font(int(h * 0.026), bold=True)
    font_item_title = get_font(int(h * 0.024), bold=True)
    font_item_desc = get_font(int(h * 0.020), bold=False)
    
    draw.text(((box_left[0]+box_left[2])/2, box_left[1]+32), "[한계] 일반 좁은 화각 (78°~90°) 문제점", font=font_box_header, fill=(255, 255, 255), anchor="mm")
    
    left_items = [
        ("1. 양옆 끝자리 인물 잘림", "테이블 좌우 팀원의 얼굴 반쪽만 송출됨"),
        ("2. 1.0m 근접 시 사각지대 발생", "좁은 허들룸 특성상 뒤로 물러설 수 없음"),
        ("3. 억지로 몸을 숙여야 함", "화면에 비치기 위해 허리를 구부정하게 기움"),
        ("4. 카메라 수동 회전 불편", "발언자마다 리모컨으로 각도를 조절해야 함")
    ]
    y_start = box_left[1] + 76
    for t, d in left_items:
        draw.text((box_left[0]+20, y_start), t, font=font_item_title, fill=(190, 18, 60))
        draw.text((box_left[0]+20, y_start+28), d, font=font_item_desc, fill=(71, 85, 105))
        y_start += 66
        
    # 3. Right Solution Card (Fully Opaque, wider to completely cover English text)
    box_right = [w*0.625, h*0.19, w*0.975, h*0.70]
    draw.rounded_rectangle(box_right, radius=14, fill=(240, 249, 255), outline=(2, 132, 199), width=3)
    # Header pill
    draw.rounded_rectangle([box_right[0]+8, box_right[1]+8, box_right[2]-8, box_right[1]+56], radius=8, fill=(2, 132, 199))
    
    draw.text(((box_right[0]+box_right[2])/2, box_right[1]+32), "[해결] 120° 초광각 커버리지 장점", font=font_box_header, fill=(255, 255, 255), anchor="mm")
    
    right_items = [
        ("1. 참석자 전원 한 화면 포착", "120° 초광각으로 좌우 사각지대 완전 제거"),
        ("2. 1.0m 근접 거리 완벽 지원", "좁은 테이블에서도 뒤로 물러설 필요 없음"),
        ("3. 자연스러운 회의 자세 유지", "몸을 기울이지 않고 바른 자세로 발언"),
        ("4. RightSight 2 자동 프레이밍", "인원수에 맞춰 카메라가 스스로 화각 최적화")
    ]
    y_start = box_right[1] + 76
    for t, d in right_items:
        draw.text((box_right[0]+20, y_start), t, font=font_item_title, fill=(3, 105, 161))
        draw.text((box_right[0]+20, y_start+28), d, font=font_item_desc, fill=(71, 85, 105))
        y_start += 66
        
    # 4. Bottom Footer Card
    draw.rounded_rectangle([w*0.16, h*0.885, w*0.84, h*0.965], radius=10, fill=(15, 23, 42), outline=(56, 189, 248), width=2)
    font_footer = get_font(int(h * 0.023), bold=True)
    draw.text((w/2, h*0.925), "[안내] 소형 룸 기준: 참석자 거리 1.0m~4.5m 이내 최적 작동 (출처: 오우션 엔지니어링 분석)", font=font_footer, fill=(255, 255, 255), anchor="mm")
    
    out_path = os.path.join(BASE_DIR, "content-system", "05_publish", "assets", "concept_huddle_fov.jpg")
    img.save(out_path, quality=95)
    sync_asset_to_all_folders("concept_huddle_fov.jpg", out_path)

# -------------------------------------------------------------
# 2. Concept: Speaker Tracking (100% Korean, Fully Opaque Overlays)
# -------------------------------------------------------------
def process_concept_speaker_tracking():
    src_base = r"C:\Users\Choijay\.gemini\antigravity-ide\brain\5ce47e1b-1367-4c9f-98c1-ec8a7c1f2880\anim_speaker_track_ppt_1790641169132.jpg"
    img = Image.open(src_base).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)
    
    # 1. Top Header Card (Fully Opaque, wider to completely cover REVOLUTIONIZING...)
    draw.rounded_rectangle([w*0.02, 18, w*0.98, 126], radius=14, fill=(15, 23, 42), outline=(56, 189, 248), width=3)
    
    font_main_title = get_font(int(h * 0.044), bold=True)
    font_sub_title = get_font(int(h * 0.023), bold=False)
    draw.text((w/2, 54), "지능형 화자 추적 메커니즘: 단순 음향 감지 vs AI 비전 융합", font=font_main_title, fill=(255, 255, 255), anchor="mm")
    draw.text((w/2, 95), "구형 음향 단독 추적의 유리벽 반사 한계 vs 듀얼 렌즈 AI 비전 + 빔포밍 TDOA 융합", font=font_sub_title, fill=(186, 230, 253), anchor="mm")
    
    # 2. Left Problem Card (Wider to completely cover .LY and ction)
    box_left = [w*0.025, h*0.19, w*0.46, h*0.70]
    draw.rounded_rectangle(box_left, radius=14, fill=(255, 245, 245), outline=(225, 29, 72), width=3)
    draw.rounded_rectangle([box_left[0]+8, box_left[1]+8, box_left[2]-8, box_left[1]+56], radius=8, fill=(225, 29, 72))
    
    font_box_header = get_font(int(h * 0.026), bold=True)
    font_item_title = get_font(int(h * 0.024), bold=True)
    font_item_desc = get_font(int(h * 0.020), bold=False)
    
    draw.text(((box_left[0]+box_left[2])/2, box_left[1]+32), "[한계] 구형 단순 음향 감지 방식 한계", font=font_box_header, fill=(255, 255, 255), anchor="mm")
    
    left_items = [
        ("1. 유리벽·벽면 반사음 오작동", "소리가 벽에 튕겨 엉뚱한 빈 공간을 비춤"),
        ("2. 발언자 전환 시 3~5초 딜레이", "소리를 계산하는 동안 화면 전환이 지연됨"),
        ("3. 덜컹거리는 급격한 모터 회전", "카메라가 휙휙 돌아가 참석자 시각 피로 유발"),
        ("4. 말 없는 참석자는 감지 불가", "조용히 듣고 있는 사람을 화면에서 배제")
    ]
    y_start = box_left[1] + 76
    for t, d in left_items:
        draw.text((box_left[0]+20, y_start), t, font=font_item_title, fill=(190, 18, 60))
        draw.text((box_left[0]+20, y_start+28), d, font=font_item_desc, fill=(71, 85, 105))
        y_start += 66

    # 3. Right Solution Card (Wider to cover English text)
    box_right = [w*0.58, h*0.19, w*0.975, h*0.70]
    draw.rounded_rectangle(box_right, radius=14, fill=(240, 249, 255), outline=(2, 132, 199), width=3)
    draw.rounded_rectangle([box_right[0]+8, box_right[1]+8, box_right[2]-8, box_right[1]+56], radius=8, fill=(2, 132, 199))
    
    draw.text(((box_right[0]+box_right[2])/2, box_right[1]+32), "[해결] 듀얼 카메라 AI 비전 + 빔포밍 융합", font=font_box_header, fill=(255, 255, 255), anchor="mm")
    
    right_items = [
        ("1. 광학 AI 인물 상시 인식", "서브 AI 뷰파인더가 사람 위치를 놓치지 않음"),
        ("2. 1초 미만 즉각 프레이밍 전환", "말하는 순간 부드럽게 메인 카메라가 포커스"),
        ("3. 반사음 없는 TDOA 삼각측량", "다중 마이크 도달 시간차로 정밀 위치 산출"),
        ("4. 개별 타일 분할(Grid View) 지원", "원격 참석자와의 동등한 회의 평등성 확보")
    ]
    y_start = box_right[1] + 76
    for t, d in right_items:
        draw.text((box_right[0]+20, y_start), t, font=font_item_title, fill=(3, 105, 161))
        draw.text((box_right[0]+20, y_start+28), d, font=font_item_desc, fill=(71, 85, 105))
        y_start += 66

    # 4. Small labels covering diagrams' English text
    # Left diagram label covering 'Glass wall'
    draw.rounded_rectangle([w*0.22, h*0.825, w*0.37, h*0.875], radius=6, fill=(15, 23, 42), outline=(225, 29, 72), width=1)
    draw.text((w*0.295, h*0.85), "[유리벽 소리 반사]", font=get_font(int(h * 0.018), bold=True), fill=(255, 255, 255), anchor="mm")
    
    # Right diagram label covering 'Hybrid vision/mic beamforming'
    draw.rounded_rectangle([w*0.60, h*0.825, w*0.83, h*0.875], radius=6, fill=(15, 23, 42), outline=(2, 132, 199), width=1)
    draw.text((w*0.715, h*0.85), "[AI 비전 + 마이크 빔포밍 융합]", font=get_font(int(h * 0.018), bold=True), fill=(255, 255, 255), anchor="mm")

    # 5. Footer Card
    draw.rounded_rectangle([w*0.16, h*0.895, w*0.84, h*0.975], radius=10, fill=(15, 23, 42), outline=(56, 189, 248), width=2)
    font_footer = get_font(int(h * 0.023), bold=True)
    draw.text((w/2, h*0.935), "[안내] 핵심 권장 환경: 참석자 거리 5.0m 이내 최적 작동 (Logitech RightSight 2 공식 가이드)", font=font_footer, fill=(255, 255, 255), anchor="mm")
    
    out_path = os.path.join(BASE_DIR, "content-system", "05_publish", "assets", "concept_speaker_tracking.jpg")
    img.save(out_path, quality=95)
    sync_asset_to_all_folders("concept_speaker_tracking.jpg", out_path)

# -------------------------------------------------------------
# 3. Pain Situation: Huddle Cutoff (100% Korean)
# -------------------------------------------------------------
def process_pain_huddle_cutoff():
    src_base = r"C:\Users\Choijay\.gemini\antigravity-ide\brain\5ce47e1b-1367-4c9f-98c1-ec8a7c1f2880\pain_huddle_cutoff_1790641564269.jpg"
    img = Image.open(src_base).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)
    
    # 1. Top Banner (Fully Opaque)
    draw.rounded_rectangle([w*0.035, 20, w*0.965, 110], radius=12, fill=(15, 23, 42), outline=(239, 68, 68), width=3)
    font_banner = get_font(int(h * 0.038), bold=True)
    draw.text((w/2, 65), "소형 회의실 좁은 웹캠(78°~90°) 사용 시 겪는 답답한 현실", font=font_banner, fill=(255, 255, 255), anchor="mm")
    
    font_bubble_title = get_font(int(h * 0.024), bold=True)
    font_bubble_desc = get_font(int(h * 0.020), bold=False)
    font_badge = get_font(int(h * 0.022), bold=True)
    
    # 2. Female Bubble (Left)
    draw.rounded_rectangle([w*0.07, h*0.13, w*0.43, h*0.25], radius=12, fill=(255, 255, 255), outline=(225, 29, 72), width=2)
    draw.text((w*0.25, h*0.165), "“카메라 화각이 너무 좁아서...", font=font_bubble_title, fill=(190, 18, 60), anchor="mm")
    draw.text((w*0.25, h*0.205), "테이블 양옆에 앉으면 둘 다 안 나와요!”", font=font_bubble_desc, fill=(30, 41, 59), anchor="mm")
    
    # 3. Male Bubble (Right)
    draw.rounded_rectangle([w*0.57, h*0.13, w*0.93, h*0.25], radius=12, fill=(255, 255, 255), outline=(225, 29, 72), width=2)
    draw.text((w*0.75, h*0.165), "“나 화면에 나와?! 억지로 숙여도", font=font_bubble_title, fill=(190, 18, 60), anchor="mm")
    draw.text((w*0.75, h*0.205), "얼굴 반쪽이랑 어깨가 계속 잘려 나가...”", font=font_bubble_desc, fill=(30, 41, 59), anchor="mm")
    
    # 4. Laptop Screen 'Meeting' label cover
    draw.rounded_rectangle([w*0.448, h*0.468, w*0.495, h*0.495], radius=3, fill=(30, 41, 59))
    draw.text((w*0.4715, h*0.4815), "화상회의", font=get_font(int(h * 0.012), bold=True), fill=(255, 255, 255), anchor="mm")
    
    # 5. Laptop screen bottom warning badge
    draw.rounded_rectangle([w*0.33, h*0.62, w*0.67, h*0.69], radius=8, fill=(225, 29, 72))
    draw.text((w*0.5, h*0.655), "[주의] 화상회의 화면: 얼굴 반쪽 & 어깨 잘림 발생", font=font_badge, fill=(255, 255, 255), anchor="mm")
    
    out_path = os.path.join(BASE_DIR, "content-system", "05_publish", "assets", "pain_huddle_cutoff.jpg")
    img.save(out_path, quality=95)
    sync_asset_to_all_folders("pain_huddle_cutoff.jpg", out_path)

# -------------------------------------------------------------
# 4. Pain Situation: Tracking Fail (100% Korean, Completely Covers English)
# -------------------------------------------------------------
def process_pain_sound_tracking_fail():
    src_base = r"C:\Users\Choijay\.gemini\antigravity-ide\brain\5ce47e1b-1367-4c9f-98c1-ec8a7c1f2880\pain_sound_tracking_fail_1790641586910.jpg"
    img = Image.open(src_base).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)
    
    # 1. Top Banner (Fully Opaque, wider)
    draw.rounded_rectangle([w*0.035, 18, w*0.965, 110], radius=12, fill=(15, 23, 42), outline=(239, 68, 68), width=3)
    font_banner = get_font(int(h * 0.038), bold=True)
    draw.text((w/2, 64), "구형 음향 추적 카메라의 오작동: 소리 반사로 빈 벽을 비추는 문제", font=font_banner, fill=(255, 255, 255), anchor="mm")
    
    font_bubble_title = get_font(int(h * 0.024), bold=True)
    font_bubble_desc = get_font(int(h * 0.020), bold=False)
    font_badge = get_font(int(h * 0.021), bold=True)
    
    # 2. Cover 'ACOUSTIC ECHO CANCELLATION?' above TV display
    draw.rounded_rectangle([w*0.045, h*0.11, w*0.335, h*0.192], radius=6, fill=(15, 23, 42), outline=(239, 68, 68), width=2)
    draw.text((w*0.19, h*0.151), "[음향 반사로 인한 추적 오류]", font=get_font(int(h * 0.017), bold=True), fill=(254, 202, 202), anchor="mm")
    
    # Cover the upper TV feed header
    draw.rounded_rectangle([w*0.055, h*0.19, w*0.33, h*0.28], radius=6, fill=(15, 23, 42), outline=(225, 29, 72), width=2)
    draw.text((w*0.1925, h*0.22), "[원격 수신 화면]", font=font_badge, fill=(254, 202, 202), anchor="mm")
    draw.text((w*0.1925, h*0.252), "발표자 대신 엉뚱한 빈 벽 송출 중", font=get_font(int(h * 0.016), bold=False), fill=(255, 255, 255), anchor="mm")
    
    # TV bottom 'NO SIGNAL' cover
    draw.rounded_rectangle([w*0.25, h*0.485, w*0.325, h*0.525], radius=4, fill=(15, 23, 42))
    draw.text((w*0.2875, h*0.505), "[오작동]", font=get_font(int(h * 0.015), bold=True), fill=(239, 68, 68), anchor="mm")

    # 3. PTZ Camera Error Tag (Top right - wide enough to cover PTZ CAMERA (False Tracking))
    draw.rounded_rectangle([w*0.68, h*0.12, w*0.97, h*0.22], radius=10, fill=(225, 29, 72), outline=(255, 255, 255), width=2)
    draw.text((w*0.825, h*0.155), "[오작동] PTZ 카메라", font=font_badge, fill=(255, 255, 255), anchor="mm")
    draw.text((w*0.825, h*0.188), "유리벽 반사음을 따라 엉뚱하게 회전 중", font=get_font(int(h * 0.016), bold=False), fill=(254, 226, 226), anchor="mm")
    
    # 4. Presenter Speech Bubble (Center-right - wide enough to cover 'TRACKING ECHO...')
    draw.rounded_rectangle([w*0.52, h*0.21, w*0.89, h*0.35], radius=12, fill=(255, 255, 255), outline=(225, 29, 72), width=3)
    draw.text((w*0.705, h*0.255), "“나 여기서 말하고 있는데...", font=font_bubble_title, fill=(190, 18, 60), anchor="mm")
    draw.text((w*0.705, h*0.30), "카메라는 왜 저 빈 벽을 비추고 있어?!”", font=font_bubble_desc, fill=(30, 41, 59), anchor="mm")
    
    # 5. Colleague Speech Bubble (Bottom-center)
    draw.rounded_rectangle([w*0.21, h*0.66, w*0.57, h*0.77], radius=12, fill=(255, 255, 255), outline=(3, 105, 161), width=3)
    draw.text((w*0.39, h*0.695), "“유리벽 소리 반사 때문에", font=font_bubble_title, fill=(3, 105, 161), anchor="mm")
    draw.text((w*0.39, h*0.735), "카메라가 엉뚱한 방향으로 돌아갔나 봐요...”", font=font_bubble_desc, fill=(30, 41, 59), anchor="mm")
    
    out_path = os.path.join(BASE_DIR, "content-system", "05_publish", "assets", "pain_sound_tracking_fail.jpg")
    img.save(out_path, quality=95)
    sync_asset_to_all_folders("pain_sound_tracking_fail.jpg", out_path)

if __name__ == "__main__":
    print("=== Processing All 4 Images with 100% Korean Text (Flawless) ===")
    process_concept_huddle_fov()
    process_concept_speaker_tracking()
    process_pain_huddle_cutoff()
    process_pain_sound_tracking_fail()
    print("=== All 4 Korean Images Generated and Deployed! ===")
