"""Logitech AI Hub 접속 + Shadow DOM 상태 진단"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

options = webdriver.ChromeOptions()
options.add_argument("--window-size=1400,1000")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

print(">> Chrome 실행 중 (headless=False)...")
driver = webdriver.Chrome(options=options)
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
})

url = "https://hub.sync.logitech.com/instant-answers"
print(f">> 페이지 접속: {url}")
driver.get(url)

wait = WebDriverWait(driver, 40)
try:
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#kapa-widget-container")))
    print(">> #kapa-widget-container 발견!")
    time.sleep(3)
except Exception as e:
    print(f">> 위젯 컨테이너 미발견: {e}")
    # 페이지 소스 일부 출력
    page_text = driver.execute_script("return document.body.innerText.substring(0, 500);")
    print(f">> 페이지 텍스트 (처음 500자):\n{page_text}")

# Shadow DOM 상세 진단
diag = driver.execute_script("""
    const result = {};
    const host = document.querySelector("#kapa-widget-container");
    result.hostExists = !!host;
    if (!host) return result;
    
    result.hasShadowRoot = !!host.shadowRoot;
    if (!host.shadowRoot) return result;
    
    const sr = host.shadowRoot;
    result.shadowChildCount = sr.children.length;
    result.shadowFirstTag = sr.firstElementChild ? sr.firstElementChild.tagName : null;
    
    // 입력창 확인
    const input = sr.querySelector("#kapa-ask-ai-input");
    result.inputExists = !!input;
    if (input) {
        result.inputTag = input.tagName;
        result.inputType = input.type || input.tagName;
        result.inputPlaceholder = input.placeholder || "";
    }
    
    // 버튼들 확인
    const buttons = sr.querySelectorAll("button");
    result.buttonCount = buttons.length;
    result.buttonTexts = [];
    buttons.forEach(b => {
        if (b.innerText.trim()) result.buttonTexts.push(b.innerText.trim().substring(0, 30));
    });
    
    // 위젯 루트 텍스트 일부
    const widgetRoot = sr.querySelector("#kapa-widget-root") || sr.firstElementChild;
    if (widgetRoot) {
        result.widgetRootText = widgetRoot.innerText.substring(0, 300);
    }
    
    return result;
""")

print("\n=== Shadow DOM 진단 결과 ===")
for k, v in diag.items():
    print(f"  {k}: {v}")

# 질문 전송 테스트
print("\n>> 질문 전송 테스트...")
input_box = driver.execute_script("""
    const host = document.querySelector("#kapa-widget-container");
    if (!host || !host.shadowRoot) return null;
    return host.shadowRoot.querySelector("#kapa-ask-ai-input");
""")

if input_box:
    question = "What is RightSight 2?"
    driver.execute_script("""
        arguments[0].click();
        arguments[0].focus();
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
    """, input_box, question)
    time.sleep(1)
    
    # 현재 input value 확인
    current_val = driver.execute_script("""
        const host = document.querySelector("#kapa-widget-container");
        const input = host.shadowRoot.querySelector("#kapa-ask-ai-input");
        return input ? input.value : "NOT_FOUND";
    """)
    print(f"  입력된 값: '{current_val}'")
    
    # 전송
    submit_btn = driver.execute_script("""
        const host = document.querySelector("#kapa-widget-container");
        const root = host.shadowRoot;
        return root.querySelector("button.mantine-ActionIcon-root") || 
               root.querySelector("button[type='submit']");
    """)
    
    if submit_btn:
        is_disabled = driver.execute_script("return arguments[0].disabled;", submit_btn)
        print(f"  전송 버튼 발견. disabled={is_disabled}")
        if not is_disabled:
            driver.execute_script("arguments[0].click();", submit_btn)
            print("  >> 전송 버튼 클릭 완료!")
    else:
        print("  >> 전송 버튼 미발견. ENTER로 전송 시도...")
        from selenium.webdriver.common.keys import Keys
        input_box.send_keys(Keys.ENTER)
    
    # 30초간 응답 모니터링
    print("\n>> 30초간 응답 상태 모니터링...")
    for i in range(10):
        time.sleep(3)
        response_text = driver.execute_script("""
            const host = document.querySelector("#kapa-widget-container");
            if (!host || !host.shadowRoot) return "NO_SHADOW";
            const wr = host.shadowRoot.querySelector("#kapa-widget-root") || host.shadowRoot.firstElementChild;
            return wr ? wr.innerText.substring(0, 500) : "NO_WIDGET_ROOT";
        """)
        has_footer = all(w in response_text for w in ["New chat", "Copy", "Good answer", "Bad answer"])
        print(f"  [{(i+1)*3}s] len={len(response_text)}, footer_complete={has_footer}")
        if has_footer:
            print(f"\n=== 응답 성공! 처음 500자 ===\n{response_text}")
            break
    else:
        print(f"\n=== 30초 후 최종 텍스트 (처음 800자) ===")
        final = driver.execute_script("""
            const host = document.querySelector("#kapa-widget-container");
            if (!host || !host.shadowRoot) return "NO_SHADOW";
            const wr = host.shadowRoot.querySelector("#kapa-widget-root") || host.shadowRoot.firstElementChild;
            return wr ? wr.innerText.substring(0, 800) : "NO_WIDGET_ROOT";
        """)
        print(final)
        
        # 각 풋터 키워드 개별 체크
        for word in ["New chat", "Copy", "Good answer", "Bad answer"]:
            print(f"  '{word}' 존재: {word in final}")
else:
    print("  >> 입력창을 찾을 수 없습니다!")

print("\n>> 10초 후 브라우저 종료...")
time.sleep(10)
driver.quit()
print(">> 완료.")
