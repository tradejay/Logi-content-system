import asyncio
import csv
import re
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

# Windows 콘솔 유니코드/이모지 출력 지원
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ==========================================
# 설정
# ==========================================
INPUT_FILE = str(Path(__file__).parent / "product_list_final.csv")
OUTPUT_FILE = str(Path(__file__).parent / "product_article_links.csv")
BASE_URL = "https://hub.sync.logitech.com"
HISTORY_LOG = Path(__file__).parent.parent / "logs" / "crawl_history.csv"

# 탭 버튼 텍스트 (URL 파라미터 대신 버튼 클릭 방식)
TAB_BUTTONS = {
    "Release Notes": "Release Notes",
    "Manuals": "Manuals",
    "FAQ & Troubleshooting": "FAQ & Troubleshooting"
}

async def prevent_korean_redirect(page, target_url):
    """ko 리디렉션 방지"""
    await page.goto(target_url, wait_until="domcontentloaded")
    if "://ko." in page.url:
        en_url = page.url.replace("://ko.", "://")
        await page.goto(en_url, wait_until="domcontentloaded")

async def click_tab_by_name(page, tab_name):
    """탭 버튼 클릭"""
    tab_button = page.locator(f"button:has-text('{tab_name}')").first
    try:
        if await tab_button.is_visible(timeout=3000):
            await tab_button.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            await tab_button.click(force=True)
            await page.wait_for_load_state("networkidle", timeout=5000)
            await asyncio.sleep(2)
            return True
    except:
        pass
    return False

async def wait_for_content(page):
    """컨텐츠 로딩 대기"""
    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
    except:
        pass
    await asyncio.sleep(3)

async def load_all_posts(page):
    """Show more 버튼 반복 클릭"""
    click_count = 0
    max_clicks = 50
    
    while click_count < max_clicks:
        try:
            btn = page.locator("button:has-text('Show more')").first
            if await btn.is_visible(timeout=2000):
                await btn.scroll_into_view_if_needed()
                await btn.click(force=True, timeout=3000)
                click_count += 1
                await asyncio.sleep(3)
            else:
                break
        except:
            break
    
    if click_count > 0:
        print(f"      ✓ Show more {click_count}회 클릭")

async def extract_articles(page, category, product_name, tab_name):
    """
    🎯 테스트 완료된 이중 파서!
    1. Manuals/FAQ: a[href] h2 → xpath=ancestor::a[1]
    2. Release Notes: div.border.border-card (fallback)
    """
    results = []
    
    # 1순위: Manuals/FAQ 스타일 (테스트 성공!)
    h2_elements = await page.locator("a[href] h2").all()
    
    for h2_el in h2_elements:
        try:
            title = await h2_el.inner_text()
            title = re.sub(r'\s+', ' ', title.strip())
            if len(title) < 5:
                continue
            
            # 테스트 확인된 셀렉터
            parent_a = h2_el.locator("xpath=ancestor::a[1]").first
            href = await parent_a.get_attribute("href") or ""
            full_link = f"{BASE_URL}{href}" if href.startswith('/') else href
            
            if full_link:
                results.append({
                    "category": category,
                    "product_name": product_name,
                    "tab_type": tab_name,
                    "article_title": title,
                    "article_url": full_link
                })
        except:
            continue
    
    # 2순위: Release Notes 스타일
    if not results:
        cards = page.locator("div.border.border-card")
        for i in range(await cards.count()):
            card = cards.nth(i)
            try:
                # 스켈레톤 스킵
                if "bg-skeleton" in (await card.get_attribute("class") or ""):
                    continue
                
                h2_el = card.locator("h2").first
                if await h2_el.count() == 0:
                    continue
                
                title = await h2_el.inner_text()
                title = re.sub(r'\s+', ' ', title.strip())
                
                link_el = card.locator("a[href]").first
                href = await link_el.get_attribute("href") or ""
                full_link = f"{BASE_URL}{href}" if href.startswith('/') else href
                
                if title and full_link:
                    results.append({
                        "category": category,
                        "product_name": product_name,
                        "tab_type": tab_name,
                        "article_title": title,
                        "article_url": full_link
                    })
            except:
                continue
    
    return results

async def main():
    """메인 실행 (전체 제품 처리)"""
    
    # 1. 제품 목록 로드
    products = []
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            products = list(reader)
        print(f"📦 {len(products)}개 제품 로드됨")
    except FileNotFoundError:
        print(f"❌ '{INPUT_FILE}' 파일 없음!")
        return
    
    # 2. CSV 초기화
    fieldnames = ["category", "product_name", "tab_type", "article_title", "article_url"]
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
    print(f"📄 '{OUTPUT_FILE}' 초기화 완료\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1600, 'height': 900},
            locale="en-US",
            geolocation={"longitude": -122.4194, "latitude": 37.7749},
            timezone_id="America/Los_Angeles",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'language', {get: () => 'en-US'});"
        )
        await context.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
        
        total = len(products)
        
        for idx, product in enumerate(products, 1):
            product_name = product['product_name']
            product_url = product['url']
            category = product['category']
            
            print(f"\n{'='*60}")
            print(f"[{idx}/{total}] {product_name}")
            print('='*60)
            
            page = await context.new_page()
            
            try:
                # 제품 페이지 접속 (ko 리디렉션 방지)
                await prevent_korean_redirect(page, product_url)
                await wait_for_content(page)
                
                # 각 탭 처리
                for tab_name in TAB_BUTTONS:
                    print(f"  📂 {tab_name}")
                    
                    # 탭 클릭
                    if not await click_tab_by_name(page, TAB_BUTTONS[tab_name]):
                        print(f"      ⚠ 탭 버튼 없음, 스킵")
                        continue
                    
                    await wait_for_content(page)
                    await load_all_posts(page)
                    
                    # 데이터 추출 (테스트 완료된 파서!)
                    items = await extract_articles(page, category, product_name, tab_name)
                    
                    if items:
                        with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8-sig') as f:
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writerows(items)
                        
                        # 히스토리 로그 저장
                        history_exists = HISTORY_LOG.exists()
                        with open(HISTORY_LOG, 'a', newline='', encoding='utf-8-sig') as f:
                            h_writer = csv.writer(f)
                            if not history_exists:
                                h_writer.writerow(["timestamp", "type", "category", "product", "title", "url", "status"])
                            
                            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            for item in items:
                                h_writer.writerow([ts, "COLLECT", item['category'], item['product_name'], item['article_title'], item['article_url'], "FOUND"])
                        
                        print(f"      ✅ {len(items)}개 저장")
                    else:
                        print(f"      ⚠ 데이터 없음")
                    
                    await asyncio.sleep(2)
                    
            except Exception as e:
                print(f"      ❌ 에러: {e}")
            finally:
                await page.close()
        
        await browser.close()
    
    print(f"\n{'='*60}")
    print(f"🎉 완료! → {OUTPUT_FILE}")
    print('='*60)

if __name__ == "__main__":
    asyncio.run(main())
