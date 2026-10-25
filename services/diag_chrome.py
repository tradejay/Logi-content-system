"""Chrome 창 가시성 테스트 - 10초간 창을 띄워놓음"""
import time
from selenium import webdriver

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
# 기존 Chrome 프로필과 충돌 방지
options.add_argument("--no-first-run")
options.add_argument("--no-default-browser-check")

print("[1] Chrome 실행 시도...")
driver = webdriver.Chrome(options=options)
print(f"[2] Chrome 실행 완료. PID 확인 중...")

# 창을 명시적으로 최대화 + 포커스
driver.maximize_window()
driver.execute_script("window.focus();")

print(f"[3] Google 접속...")
driver.get("https://www.google.com")
time.sleep(2)
print(f"[4] 페이지 로드 완료: {driver.title}")
print(f"[5] 창 크기: {driver.get_window_size()}")
print(f"[6] 창 위치: {driver.get_window_position()}")

print("\n>> 10초간 창을 유지합니다. 화면에 Chrome 창이 보이는지 확인해주세요!")
for i in range(10, 0, -1):
    print(f"   {i}초 남음...", flush=True)
    time.sleep(1)

driver.quit()
print("\n>> 브라우저 종료.")
