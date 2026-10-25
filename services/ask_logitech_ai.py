"""
Logitech AI Server (Stealth Mode)
---------------------------------
Logitech AI에 질문을 던지고 답변을 수집하기 위해 Chrome 브라우저를 백그라운드 서버 모드로 상시 가동하는 스크립트입니다.
실행 방법: python ask_logitech_ai.py [--port 포트번호]
"""

import time
import argparse
import os
import json
import http.server
import socketserver
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException, WebDriverException

class LogitechAI:
    def __init__(self, headless=False):
        self.headless = headless
        self.start_driver()

    def start_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--window-size=1400,1000")
        if self.headless:
            options.add_argument("--headless=new")
        
        # 자동화 감지 우회 설정
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        print(">> 브라우저 Stealth 모드로 실행 중...", flush=True)
        try:
            self.driver = webdriver.Chrome(options=options)
            
            # navigator.webdriver 속성 우회
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            
            self.wait = WebDriverWait(self.driver, 40)
            self.url = "https://hub.sync.logitech.com/instant-answers"
            self.driver.get(self.url)
            
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#kapa-widget-container")))
            time.sleep(3)
        except Exception as e:
            print(f">> 드라이버 시작 중 오류 발생: {e}")
            raise RuntimeError('Logitech browser initialization failed') from None

    def reinit_driver(self):
        print("\n>> [세션 복구] 브라우저 세션을 재시작합니다...", flush=True)
        try:
            self.driver.quit()
        except:
            pass
        time.sleep(2)
        self.start_driver()

    def reset_chat(self, retry=True):
        print(">> 채팅 세션 초기화 시도...", flush=True)
        try:
            # 1. New chat 버튼 클릭 시도
            clicked = self.driver.execute_script("""
                const host = document.querySelector("#kapa-widget-container");
                if (!host || !host.shadowRoot) return false;
                const buttons = host.shadowRoot.querySelectorAll("button");
                for (let btn of buttons) {
                    const text = btn.innerText || "";
                    const aria = btn.getAttribute("aria-label") || "";
                    if (text.includes("New chat") || aria.includes("New chat")) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            """)
            
            cleared = False
            if clicked:
                for _ in range(6):
                    time.sleep(0.5)
                    copy_exists = self.driver.execute_script("""
                        const host = document.querySelector("#kapa-widget-container");
                        if (!host || !host.shadowRoot) return false;
                        return !!host.shadowRoot.querySelector("button[aria-label='Copy']");
                    """)
                    if not copy_exists:
                        cleared = True
                        break
            
            # 2. 버튼이 없거나 화면이 초기화되지 않았다면 페이지 새로고침으로 확실한 새 세션 보장
            if not cleared:
                print(">> 페이지를 새로고침하여 깨끗한 새 대화 세션을 시작합니다...", flush=True)
                self.driver.get(self.url)
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#kapa-widget-container")))
                time.sleep(2)
            else:
                print(">> 새 대화 세션 준비 완료.", flush=True)
        except (InvalidSessionIdException, NoSuchWindowException, WebDriverException) as e:
            if retry:
                self.reinit_driver()
                self.reset_chat(retry=False)
            else:
                print(f">> 채팅 초기화 실패: {e}")
        except Exception as e:
            print(f">> 초기화 중 오류 발생: {e}")

    def ask(self, question, retry=True):
        self.last_error = None
        print(f"\n[AI 질문 시작] {question}", flush=True)
        try:
            input_box = self.driver.execute_script("""
                const host = document.querySelector("#kapa-widget-container");
                if (!host || !host.shadowRoot) return null;
                return host.shadowRoot.querySelector("#kapa-ask-ai-input");
            """)
            
            if not input_box:
                print(">> 입력창 탐색 실패. 새로고침합니다.", flush=True)
                self.driver.refresh()
                time.sleep(5)
                if retry: return self.ask(question, retry=False)
                return None

            # 질문 전송 전, 기존에 렌더링된 복사 버튼 개수를 기록 (이전 대화와 혼동 방지)
            initial_copy_count = self.driver.execute_script("""
                const host = document.querySelector("#kapa-widget-container");
                if (!host || !host.shadowRoot) return 0;
                return host.shadowRoot.querySelectorAll("button[aria-label='Copy']").length;
            """) or 0

            # React/Mantine 호환 입력 방식 (Textarea 및 Input 프로토타입 모두 대응 + Shadow DOM composed 이벤트)
            self.driver.execute_script("""
                const input = arguments[0];
                const text = arguments[1];
                input.focus();
                input.click();
                
                // 1. Prototype 판별 (HTMLTextAreaElement vs HTMLInputElement)
                const proto = Object.getPrototypeOf(input);
                let setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                if (!setter) {
                    if (window.HTMLTextAreaElement && input instanceof HTMLTextAreaElement) {
                        setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
                    } else {
                        setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                    }
                }
                
                if (setter) {
                    setter.call(input, text);
                } else {
                    input.value = text;
                }
                
                // React 내부 valueTracker 강제 리셋 (값 변경 감지용)
                if (input._valueTracker) {
                    input._valueTracker.setValue('');
                }
                
                // Shadow DOM 경계를 넘을 수 있도록 composed: true 이벤트 디스패치
                input.dispatchEvent(new Event('input', { bubbles: true, composed: true, cancelable: true }));
                input.dispatchEvent(new Event('change', { bubbles: true, composed: true, cancelable: true }));
                try {
                    input.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, inputType: 'insertText', data: text }));
                } catch(e) {}
            """, input_box, question)
            time.sleep(0.5)

            # 실 사용자 키 입력 시뮬레이션: 스페이스바 입력으로 Mantine 버튼 활성화 트리거 후 백스페이스
            try:
                actions = ActionChains(self.driver)
                actions.click(input_box).send_keys(" ").send_keys(Keys.BACK_SPACE).perform()
            except Exception as e:
                print(f">> 키보드 이벤트 보조 전송: {e}", flush=True)

            time.sleep(0.8)
            
            # 전송 버튼 탐색 (Attach files 버튼 제외, arrow-up 아이콘 및 data-variant='filled' 버튼 타겟팅)
            submit_btn = self.driver.execute_script("""
                const host = document.querySelector("#kapa-widget-container");
                if (!host || !host.shadowRoot) return null;
                const root = host.shadowRoot;
                const arrowSvg = root.querySelector("svg.tabler-icon-arrow-up");
                if (arrowSvg) {
                    const btn = arrowSvg.closest("button");
                    if (btn) return btn;
                }
                const filledBtn = root.querySelector("button.mantine-ActionIcon-root[data-variant='filled']");
                if (filledBtn) return filledBtn;
                for (let b of root.querySelectorAll("button.mantine-ActionIcon-root")) {
                    if (b.getAttribute("aria-label") !== "Attach files") return b;
                }
                return root.querySelector("button[type='submit']");
            """)
            
            is_enabled = False
            if submit_btn:
                for _ in range(15):
                    is_disabled = self.driver.execute_script("""
                        const host = document.querySelector("#kapa-widget-container");
                        if (!host || !host.shadowRoot) return true;
                        const root = host.shadowRoot;
                        const arrowSvg = root.querySelector("svg.tabler-icon-arrow-up");
                        const btn = (arrowSvg ? arrowSvg.closest("button") : null) || 
                                    root.querySelector("button.mantine-ActionIcon-root[data-variant='filled']") ||
                                    root.querySelector("button[type='submit']");
                        if (!btn) return true;
                        return btn.disabled || btn.hasAttribute('disabled') || btn.getAttribute('data-disabled') === 'true';
                    """)
                    if not is_disabled:
                        is_enabled = True
                        break
                    time.sleep(0.2)

            if submit_btn and is_enabled:
                self.driver.execute_script("arguments[0].click();", submit_btn)
            else:
                # 폴백: ActionChains로 엔터 키 전송
                try:
                    ActionChains(self.driver).click(input_box).send_keys(Keys.ENTER).perform()
                except Exception:
                    input_box.send_keys(Keys.ENTER)
                
            print(">> 질문 전송 완료. AI 답변을 대기합니다...", flush=True)

            ai_response = ""
            start_time = time.time()
            
            # 긴 답변 스트리밍 대응을 위해 대기 시간을 240초(4분)로 확대
            while time.time() - start_time < 240:
                # 봇 차단 및 CAPTCHA 감지
                detection_check = """
                    const host = document.querySelector("#kapa-widget-container");
                    if (!host || !host.shadowRoot) return false;
                    const alert = host.shadowRoot.querySelector(".mantine-Alert-root");
                    if (alert && alert.innerText.includes("unusual activity")) return true;
                    return false;
                """
                if self.driver.execute_script(detection_check):
                    print("\n>> [경고] 봇 감지 발생. 브라우저에서 CAPTCHA를 수동 해결해 주세요 (60초 대기)...", flush=True)
                    captcha_solved = False
                    for _ in range(30):
                        time.sleep(2)
                        try:
                            if not self.driver.execute_script(detection_check):
                                print(">> [성공] 봇 감지 해제.", flush=True)
                                captcha_solved = True
                                break
                        except Exception:
                            break
                    if not captcha_solved:
                        print(">> [실패] CAPTCHA 미해결.", flush=True)
                        self.last_error = 'captcha_required'
                        return None

                result = self.driver.execute_script("""
                    const host = document.querySelector("#kapa-widget-container");
                    if (!host || !host.shadowRoot) return null;
                    const root = host.shadowRoot;
                    const initialCount = arguments[0];
                    
                    // 새 답변 완료 지표: 복사 버튼 개수가 질문 전보다 증가했는지 확인!
                    const copyButtons = root.querySelectorAll("button[aria-label='Copy']");
                    const goodButtons = root.querySelectorAll("button[aria-label='Good answer']");
                    const isDone = (copyButtons.length > initialCount) || (goodButtons.length > initialCount);
                    
                    // 가장 최신의(마지막) 순수 AI 답변 본문 추출 (.mantine-gwax9f)
                    const answerContainers = root.querySelectorAll(".mantine-gwax9f");
                    let answerText = "";
                    if (answerContainers.length > 0) {
                        answerText = answerContainers[answerContainers.length - 1].innerText;
                    }
                    
                    // 폴백: 전체 위젯 텍스트
                    const widgetRoot = root.querySelector("#kapa-widget-root") || root.firstElementChild;
                    const fullText = widgetRoot ? widgetRoot.innerText : "";
                    
                    return {
                        isDone: isDone,
                        answerText: answerText,
                        fullText: fullText
                    };
                """, initial_copy_count)
                
                if result and result.get("isDone"):
                    final_answer = result.get("answerText") or result.get("fullText")
                    if final_answer and len(final_answer.strip()) > 10:
                        print(">> [성공] AI 답변 수신 완료!", flush=True)
                        self.save_response(question, final_answer)
                        return final_answer
                
                time.sleep(2)

            print("\n[실패] 답변 대기 시간 초과 또는 미완성.")
            return None

        except (InvalidSessionIdException, NoSuchWindowException, WebDriverException) as e:
            if retry:
                self.reinit_driver()
                return self.ask(question, retry=False)
            else:
                print(f"\n[오류] 세션 복구 실패: {e}")
                return None
        except Exception as e:
            print(f"\n[오류] {e}")
            return None

    def save_response(self, question, ai_response):
        results_dir = "ai_results"
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(results_dir, f"response_{timestamp}.txt")
        
        content = f"질문: {question}\n{'='*50}\n{ai_response}"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        with open("logitech_ai_response.txt", "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"\n[성공] 답변 저장 완료: {output_file}")

    def close(self):
        try:
            self.driver.quit()
        except:
            pass

class LogitechAIHandler(http.server.BaseHTTPRequestHandler):
    bot = None

    def do_GET(self):
        if self.path != '/health':
            self.send_error(404)
            return
        try:
            ready = bool(self.bot.driver.execute_script('const h=document.querySelector("#kapa-widget-container"); return !!(h && h.shadowRoot && h.shadowRoot.querySelector("#kapa-ask-ai-input"));'))
        except Exception:
            ready = False
        body = json.dumps({'status': 'ready' if ready else 'unavailable'}).encode()
        self.send_response(200 if ready else 503)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == '/ask':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                question = data.get('question')

                print(f"\n[API 요청 수신] 질문: {question}")
                self.bot.reset_chat()
                response = self.bot.ask(question)

                res_body = json.dumps({'response': response, 'status': 'success' if response else 'error',
                                      'reason': getattr(self.bot, 'last_error', None)})
                res_bytes = res_body.encode('utf-8')

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(res_bytes)))
                self.end_headers()
                self.wfile.write(res_bytes)
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                print(">> [알림] 클라이언트가 응답 수신 전 연결을 먼저 종료했습니다 (클라이언트 측 타임아웃 초과 추정).")
            except Exception as e:
                print(f">> 서버 내부 오류: {e}")
                try:
                    err_bytes = json.dumps({'error': str(e)}).encode('utf-8')
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', str(len(err_bytes)))
                    self.end_headers()
                    self.wfile.write(err_bytes)
                except Exception:
                    pass
        else:
            self.send_response(404)
            self.end_headers()

def run_server(bot, port=5000):
    LogitechAIHandler.bot = bot
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), LogitechAIHandler) as httpd:
        print(f"\n>> Logitech AI API 서버 작동 중 (포트: {port})")
        httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Logitech AI Server Mode")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the API server on")
    parser.add_argument('--headless', action='store_true', help='Run background browser without a visible window')
    args = parser.parse_args()
    
    bot = LogitechAI(headless=args.headless)
    try:
        run_server(bot, args.port)
    finally:
        bot.close()
