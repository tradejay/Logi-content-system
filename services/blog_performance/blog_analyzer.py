"""
Naver Blog Analyzer & Index Calculation Engine
Handles:
1. Naver visitor counter XML parsing (NVisitorgp4Ajax.nhn)
2. Blog RSS XML parsing (rss.blog.naver.com)
3. Blog Index / Optimization Grade calculation algorithm
4. Naver Search API & Search scraping rank tracker
5. Naver SearchAd API (HMAC-SHA256 signature) & Autocomplete keyword engine
6. Naver DataLab Trend API
"""

import time
import base64
import hmac
import hashlib
import json
import os
import re
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(BASE_DIR, "config", "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "naver_client_id": "",
        "naver_client_secret": "",
        "ad_api_key": "",
        "ad_secret_key": "",
        "ad_customer_id": ""
    }

def save_config(data):
    config = load_config()
    config.update(data)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return config

headers_common = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 1. Fetch Naver Daily Visitors (Public AJAX API)
def get_daily_visitors(blog_id):
    """
    Calls https://blog.naver.com/NVisitorgp4Ajax.nhn?blogId={blog_id}
    Returns list of {'date': 'YYYY-MM-DD', 'visitor_count': int} for the last 5 days.
    """
    url = f"https://blog.naver.com/NVisitorgp4Ajax.nhn?blogId={blog_id}"
    try:
        res = requests.get(url, headers=headers_common, timeout=6)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            visitors = []
            for item in root.findall("visitorcnt"):
                id_date = item.attrib.get("id", "")
                cnt_str = item.attrib.get("cnt", "0")
                if len(id_date) == 8:
                    formatted_date = f"{id_date[:4]}-{id_date[4:6]}-{id_date[6:]}"
                else:
                    formatted_date = id_date
                visitors.append({
                    "date": formatted_date,
                    "visitor_count": int(cnt_str)
                })
            visitors.sort(key=lambda x: x["date"])
            return visitors
    except Exception as e:
        print(f"Error fetching visitors for {blog_id}: {e}")
    return []

# 2. Fetch Blog RSS Feed (Recent Posts & Publishing Frequency)
def get_blog_rss_info(blog_id):
    """
    Parses https://rss.blog.naver.com/{blog_id}.xml
    Returns blog title, link, description, and list of recent posts (up to 30)
    """
    url = f"https://rss.blog.naver.com/{blog_id}.xml"
    try:
        res = requests.get(url, headers=headers_common, timeout=6)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            channel = root.find("channel")
            if channel is None:
                return None
            
            blog_title = channel.findtext("title", default="네이버 블로그")
            blog_link = channel.findtext("link", default=f"https://blog.naver.com/{blog_id}")
            blog_desc = channel.findtext("description", default="")
            
            items = channel.findall("item")
            posts = []
            for item in items:
                title = item.findtext("title", default="").strip()
                link = item.findtext("link", default="")
                pub_date = item.findtext("pubDate", default="")
                desc = item.findtext("description", default="")
                # Clean html tags from description snippet
                clean_snippet = re.sub(r"<[^>]+>", "", desc).strip()
                
                posts.append({
                    "title": title,
                    "link": link,
                    "pub_date": pub_date,
                    "snippet": clean_snippet[:150] + "..." if len(clean_snippet) > 150 else clean_snippet
                })
            
            return {
                "blog_id": blog_id,
                "title": blog_title,
                "link": blog_link,
                "description": blog_desc,
                "post_count_recent": len(posts),
                "posts": posts
            }
    except Exception as e:
        print(f"Error fetching RSS for {blog_id}: {e}")
    return None

# 3. Blog Index & Optimization Grade Calculator
def calculate_blog_index(visitor_data, rss_data, rank_sample_ratio=None):
    """
    Calculates estimated Blog Index (0 ~ 1000 pts) and Optimization Grade.
    Evaluation Dimensions:
    1. Traffic Score (방문자 유입 점수): 0~250
    2. Activity Score (활동성/주기 점수): 0~250
    3. Content Volume & Quality (콘텐츠 생산성): 0~250
    4. Exposure & Stability (검색 노출력 및 안정성): 0~250
    Total Score: 0~1000
    Grades:
    - 0 ~ 299: 일반 블로그 (새싹/초기)
    - 300 ~ 449: 준최적화 1~2단계
    - 450 ~ 599: 준최적화 3~4단계
    - 600 ~ 719: 준최적화 5~6단계
    - 720 ~ 829: 최적화 1단계
    - 830 ~ 919: 최적화 2단계
    - 920 ~ 1000: 최적화 3~4+단계 (파워/인플루언서급)
    """
    # 1. Traffic Score (Max 250)
    avg_visitors = 0
    recent_visitors_sum = 0
    if visitor_data:
        counts = [v["visitor_count"] for v in visitor_data]
        recent_visitors_sum = sum(counts)
        avg_visitors = recent_visitors_sum / len(counts) if counts else 0
    
    if avg_visitors >= 5000:
        traffic_score = 250
    elif avg_visitors >= 2000:
        traffic_score = 210 + int((avg_visitors - 2000) / 3000 * 40)
    elif avg_visitors >= 800:
        traffic_score = 170 + int((avg_visitors - 800) / 1200 * 40)
    elif avg_visitors >= 300:
        traffic_score = 130 + int((avg_visitors - 300) / 500 * 40)
    elif avg_visitors >= 100:
        traffic_score = 90 + int((avg_visitors - 100) / 200 * 40)
    elif avg_visitors >= 30:
        traffic_score = 50 + int((avg_visitors - 30) / 70 * 40)
    else:
        traffic_score = max(10, int(avg_visitors * 1.5))

    # 2. Activity Score (Max 250)
    # Based on days since last post and post frequency in recent posts
    activity_score = 100
    days_since_last_post = 999
    posting_frequency_weekly = 0
    
    if rss_data and rss_data.get("posts"):
        posts = rss_data["posts"]
        num_posts = len(posts)
        
        # Parse publication dates
        dates = []
        for p in posts:
            p_date_str = p.get("pub_date", "")
            try:
                # Format: "Mon, 21 Sep 2026 14:00:00 +0900" or similar RFC 822
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(p_date_str)
                dates.append(dt)
            except Exception:
                pass
        
        if dates:
            now = datetime.now(dates[0].tzinfo) if dates[0].tzinfo else datetime.now()
            days_since_last_post = (now - dates[0]).days
            
            # Posts within last 7 days and 30 days
            last_7_days_count = sum(1 for d in dates if (now - d).days <= 7)
            posting_frequency_weekly = last_7_days_count
            
            # Score based on freshness
            if days_since_last_post <= 1:
                freshness_pts = 100
            elif days_since_last_post <= 3:
                freshness_pts = 85
            elif days_since_last_post <= 7:
                freshness_pts = 70
            elif days_since_last_post <= 14:
                freshness_pts = 45
            else:
                freshness_pts = 20
            
            # Score based on weekly volume
            if last_7_days_count >= 5:
                freq_pts = 150
            elif last_7_days_count >= 3:
                freq_pts = 130
            elif last_7_days_count >= 1:
                freq_pts = 100
            else:
                freq_pts = 40
            
            activity_score = min(250, freshness_pts + freq_pts)
        else:
            activity_score = 120

    # 3. Content Volume & Quality Score (Max 250)
    # Evaluates title length, description snippet richness, diversity
    content_score = 150
    if rss_data and rss_data.get("posts"):
        posts = rss_data["posts"]
        avg_title_len = sum(len(p["title"]) for p in posts) / len(posts) if posts else 0
        avg_snip_len = sum(len(p.get("snippet", "")) for p in posts) / len(posts) if posts else 0
        
        # Good titles: 15~40 chars
        title_quality = 70 if (15 <= avg_title_len <= 50) else 45
        # Rich snippets: > 100 chars
        snippet_quality = 80 if avg_snip_len >= 100 else 50
        # Post quantity consistency
        consistency = 100 if len(posts) >= 15 else (len(posts) * 6)
        
        content_score = min(250, title_quality + snippet_quality + consistency)

    # 4. Exposure & Stability Score (Max 250)
    # If rank_sample_ratio is provided (percentage of sample keywords in top 10/20),
    # use it; otherwise infer from visitor consistency & baseline
    if rank_sample_ratio is not None:
        exposure_score = int(rank_sample_ratio * 250)
    else:
        # Estimated based on visitors and publishing consistency
        exposure_score = min(250, int((traffic_score * 0.6) + (activity_score * 0.4)))

    total_score = traffic_score + activity_score + content_score + exposure_score
    total_score = max(50, min(1000, total_score))

    # Determine Grade
    if total_score >= 920:
        grade = "최적화 3+ (파워/인플루언서급)"
        grade_badge = "opt-high"
        level = "Lv. 최적3+"
    elif total_score >= 830:
        grade = "최적화 2단계"
        grade_badge = "opt-2"
        level = "Lv. 최적2"
    elif total_score >= 720:
        grade = "최적화 1단계"
        grade_badge = "opt-1"
        level = "Lv. 최적1"
    elif total_score >= 620:
        grade = "준최적화 5~6단계"
        grade_badge = "semi-3"
        level = "Lv. 준최5~6"
    elif total_score >= 480:
        grade = "준최적화 3~4단계"
        grade_badge = "semi-2"
        level = "Lv. 준최3~4"
    elif total_score >= 320:
        grade = "준최적화 1~2단계"
        grade_badge = "semi-1"
        level = "Lv. 준최1~2"
    else:
        grade = "일반 블로그 (초기 육성 단계)"
        grade_badge = "normal"
        level = "Lv. 일반"

    # Actionable suggestions
    recommendations = []
    if days_since_last_post > 3:
        recommendations.append("최근 포스팅 주기가 다소 길어졌습니다. 주 3회 이상의 규칙적인 발행이 블로그 지수 상승에 유리합니다.")
    if avg_visitors < 100:
        recommendations.append("검색량이 높은 대형 키워드보다는 경쟁이 적고 검색량이 월 500~2,000회인 세부(롱테일) 키워드 공략을 추천합니다.")
    if activity_score > 200 and avg_visitors < 300:
        recommendations.append("포스팅은 성실히 이루어지고 있으나 검색 유입 키워드 배치가 부족할 수 있습니다. 제목에 핵심 검색어를 전진 배치하세요.")
    if total_score >= 720:
        recommendations.append("최적화 단계에 진입하여 메인 키워드 상위 노출 경쟁력이 충분합니다. 챌린지 프로그램 및 인플루언서 검색 등록을 추천합니다.")
    if not recommendations:
        recommendations.append("현재 전반적인 지표 밸런스가 매우 양호합니다. 현재의 발행 주기와 콘텐츠 퀄리티를 유지하세요.")

    return {
        "total_score": total_score,
        "grade": grade,
        "grade_badge": grade_badge,
        "level": level,
        "traffic_score": traffic_score,
        "activity_score": activity_score,
        "content_score": content_score,
        "exposure_score": exposure_score,
        "avg_daily_visitors": round(avg_visitors, 1),
        "weekly_posts": posting_frequency_weekly,
        "days_since_last_post": days_since_last_post if days_since_last_post != 999 else "기록 없음",
        "recommendations": recommendations
    }

def post_identity(url):
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url or "")
    if parsed.hostname not in {"blog.naver.com", "m.blog.naver.com"}:
        return None
    parts = parsed.path.strip("/").split("/")
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0].lower(), parts[1]
    query = parse_qs(parsed.query)
    if query.get("blogId") and query.get("logNo"):
        return query["blogId"][0].lower(), query["logNo"][0]
    return None


def matches_target(link, bloggerlink, blog_id, target_url=None):
    from urllib.parse import urlparse
    identity = post_identity(link)
    if target_url:
        expected = post_identity(target_url)
        return expected is not None and identity == expected and identity[0] == blog_id
    if identity:
        return identity[0] == blog_id
    parsed = urlparse(bloggerlink or "")
    return parsed.hostname in {"blog.naver.com", "m.blog.naver.com"} and parsed.path.strip("/").lower() == blog_id


def parse_search_api_items(items, keyword, clean_blog_id, source="api", target_url=None):
    target_rank = None
    target_title = None
    target_link = None
    top_posts = []

    for i, item in enumerate(items):
        link = item.get("link", "")
        title = re.sub(r"<[^>]+>", "", item.get("title", ""))
        bloggername = item.get("bloggername", "")
        bloggerlink = item.get("bloggerlink", "")
        
        if i < 10:
            top_posts.append({
                "rank": i + 1,
                "title": title,
                "link": link,
                "bloggername": bloggername,
                "postdate": item.get("postdate", "")
            })

        if clean_blog_id and matches_target(link, bloggerlink, clean_blog_id, target_url):
            if target_rank is None:
                target_rank = i + 1
                target_title = title
                target_link = link

    return {
        "source": source,
        "keyword": keyword,
        "blog_id": clean_blog_id,
        "rank": target_rank,
        "target_title": target_title,
        "target_link": target_link,
        "total_searched": len(items),
        "top_posts": top_posts
    }

# 4. Search Rank Checker (1 ~ 100 Rank)
def check_keyword_rank(keyword, blog_id, client_id="", client_secret="", target_url=None):
    """
    Finds where blog_id ranks (1 ~ 100) for given keyword.
    Tries Naver Open API if credentials present, otherwise falls back to Web Scraping.
    Returns:
    {
        'keyword': keyword,
        'blog_id': blog_id,
        'rank': int or None,
        'post_title': str,
        'post_link': str,
        'top_posts': list of top 10 results
    }
    """
    keyword = keyword.strip()
    if not keyword:
        return {"error": "키워드를 입력해주세요."}

    clean_blog_id = blog_id.lower().strip() if blog_id else ""

    # Attempt 1: Naver API (Supports both new NAVER API HUB and legacy Naver Developers Center)
    if client_id and client_secret:
        # 1-A: New NAVER API HUB (apigw.ntruss.com - post July 2026 migration)
        try:
            hub_url = f"https://naverapihub.apigw.ntruss.com/search/v1/blog?query={requests.utils.quote(keyword)}&display=100&sort=sim"
            hub_headers = {
                "X-NCP-APIGW-API-KEY-ID": client_id,
                "X-NCP-APIGW-API-KEY": client_secret,
                "User-Agent": headers_common["User-Agent"]
            }
            res_hub = requests.get(hub_url, headers=hub_headers, timeout=6)
            if res_hub.status_code == 200:
                data = res_hub.json()
                items = data.get("items", [])
                return parse_search_api_items(items, keyword, clean_blog_id, source="naver_api_hub", target_url=target_url)
        except Exception as e:
            print(f"NAVER API HUB call error: {e}")

        # 1-B: Legacy Naver Developers Center (openapi.naver.com - pre-July grandfathered)
        try:
            url = f"https://openapi.naver.com/v1/search/blog.json?query={requests.utils.quote(keyword)}&display=100&sort=sim"
            headers = {
                "X-Naver-Client-Id": client_id,
                "X-Naver-Client-Secret": client_secret,
                "User-Agent": headers_common["User-Agent"]
            }
            res = requests.get(url, headers=headers, timeout=6)
            if res.status_code == 200:
                data = res.json()
                items = data.get("items", [])
                return parse_search_api_items(items, keyword, clean_blog_id, source="legacy_developer_center", target_url=target_url)
        except Exception as e:
            print(f"Naver Search API call error: {e}, falling back to scraping")

    # Attempt 2: Robust Web Scraping Fallback
    try:
        top_posts = []
        target_rank = None
        target_title = None
        target_link = None
        seen_urls = set()
        all_posts = []

        # Scrape up to 3 pages
        for page in range(1, 4):
            start_num = (page - 1) * 30 + 1
            search_url = f"https://search.naver.com/search.naver?where=blog&query={requests.utils.quote(keyword)}&sm=tab_pge&start={start_num}"
            resp = requests.get(search_url, headers=headers_common, timeout=6)
            if resp.status_code != 200:
                break
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Find all blog post links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                m = re.search(r"blog\.naver\.com/([a-zA-Z0-9_\-]+)/([0-9]+)", href)
                if m:
                    b_id = m.group(1)
                    post_id = m.group(2)
                    clean_post_url = f"https://blog.naver.com/{b_id}/{post_id}"
                    
                    if clean_post_url not in seen_urls:
                        seen_urls.add(clean_post_url)
                        
                        # Find title: get text of this link or parent container
                        title_text = a.get_text(strip=True)
                        if len(title_text) < 5:
                            parent = a.find_parent("div") or a.find_parent("li")
                            if parent:
                                cand_titles = [t.get_text(strip=True) for t in parent.find_all(["a", "span", "strong"]) if len(t.get_text(strip=True)) > 8]
                                if cand_titles:
                                    title_text = cand_titles[0]
                        
                        all_posts.append({
                            "rank": len(all_posts) + 1,
                            "blog_id": b_id,
                            "title": title_text if title_text else f"블로그 포스트 ({post_id})",
                            "link": clean_post_url,
                            "bloggername": b_id
                        })

            if len(all_posts) >= 90:
                break

        # Check ranking for target blog_id
        for post in all_posts:
            if post["rank"] <= 10:
                top_posts.append({
                    "rank": post["rank"],
                    "title": post["title"],
                    "link": post["link"],
                    "bloggername": post["bloggername"],
                    "postdate": ""
                })

            if clean_blog_id and matches_target(post["link"], "", clean_blog_id, target_url):
                if target_rank is None:
                    target_rank = post["rank"]
                    target_title = post["title"]
                    target_link = post["link"]

        return {
            "source": "scraping",
            "keyword": keyword,
            "blog_id": blog_id,
            "rank": target_rank,
            "target_title": target_title,
            "target_link": target_link,
            "total_searched": len(all_posts),
            "top_posts": top_posts
        }
    except Exception as e:
        print(f"Scraping error: {e}")
        return {
            "error": f"검색 결과를 수집하는 중 오류가 발생했습니다: {str(e)}",
            "keyword": keyword,
            "blog_id": blog_id,
            "rank": None,
            "top_posts": []
        }

# 5. Naver SearchAd API (Keyword Volume & Competition)
def get_signature(timestamp, method, path, secret_key):
    message = f"{timestamp}.{method}.{path}"
    hash_obj = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
    return base64.b64encode(hash_obj.digest()).decode("utf-8")

def get_searchad_keywords(hint_keyword, api_key="", secret_key="", customer_id=""):
    """
    Calls Naver SearchAd API (/keywordstool) to get monthly PC/Mobile search volumes,
    clicks, CTR, and competition level.
    If keys are not configured, falls back to Naver Autocomplete + estimated metrics.
    """
    hint_keyword = hint_keyword.strip()
    if not hint_keyword:
        return []

    # Attempt 1: Official SearchAd API
    if api_key and secret_key and customer_id:
        try:
            timestamp = str(round(time.time() * 1000))
            path = "/keywordstool"
            signature = get_signature(timestamp, "GET", path, secret_key)
            
            headers = {
                "X-Timestamp": timestamp,
                "X-API-KEY": api_key,
                "X-Customer": str(customer_id),
                "X-Signature": signature
            }
            url = f"https://api.searchad.naver.com{path}?hintKeywords={requests.utils.quote(hint_keyword)}&showDetail=1"
            res = requests.get(url, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                raw_list = data.get("keywordList", [])
                
                results = []
                for k in raw_list[:25]:
                    rel_kw = k.get("relKeyword", "")
                    
                    # Search counts can be "< 10" string
                    pc_cnt = k.get("monthlyPcQcCnt", 0)
                    mo_cnt = k.get("monthlyMobileQcCnt", 0)
                    
                    pc_val = int(pc_cnt) if str(pc_cnt).isdigit() else None
                    mo_val = int(mo_cnt) if str(mo_cnt).isdigit() else None
                    total_cnt = pc_val + mo_val if pc_val is not None and mo_val is not None else None
                    
                    results.append({
                        "keyword": rel_kw,
                        "monthly_pc": pc_cnt,
                        "monthly_mobile": mo_cnt,
                        "monthly_total": total_cnt,
                        "monthly_ave_pc_clk_cnt": k.get("monthlyAvePcClkCnt", 0),
                        "monthly_ave_mobile_clk_cnt": k.get("monthlyAveMobileClkCnt", 0),
                        "monthly_ave_pc_ctr": k.get("monthlyAvePcCtr", 0),
                        "monthly_ave_mobile_ctr": k.get("monthlyAveMobileCtr", 0),
                        "comp_idx": k.get("compIdx", "보통"),
                        "source": "official_ad_api"
                    })
                return results
        except Exception as e:
            print(f"SearchAd API error: {e}, falling back to suggestions")

    # Attempt 2: Smart Autocomplete / Related Keywords Fallback
    try:
        # Naver Autocomplete API
        ac_url = f"https://ac.search.naver.com/nx/ac?q={requests.utils.quote(hint_keyword)}&con=1&frm=nv&ans=2&r_format=json&r_enc=UTF-8&r_unicode=0&t_koreng=1&run=2&rev=4&q_enc=UTF-8&st=100"
        res = requests.get(ac_url, headers=headers_common, timeout=6)
        suggested_keywords = [hint_keyword]
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", [[]])
            if items and len(items) > 0:
                for sublist in items[0]:
                    if sublist and len(sublist) > 0:
                        suggested_keywords.append(sublist[0])
        
        # Deduplicate
        unique_kws = []
        for kw in suggested_keywords:
            if kw not in unique_kws:
                unique_kws.append(kw)
        
        # Autocomplete supplies suggestions, not measured search metrics.
        results = [{
            "keyword": kw,
            "monthly_pc": None, "monthly_mobile": None, "monthly_total": None,
            "monthly_ave_pc_clk_cnt": None, "monthly_ave_mobile_clk_cnt": None,
            "monthly_ave_pc_ctr": None, "monthly_ave_mobile_ctr": None,
            "comp_idx": None, "source": "autocomplete", "measurement_status": "unavailable"
        } for kw in unique_kws[:20]]
        return results
    except Exception as e:
        print(f"Autocomplete error: {e}")
        return []

# 6. Naver DataLab Search Trend API
def get_datalab_trend(keywords, start_date=None, end_date=None, time_unit="date", client_id="", client_secret=""):
    """
    Calls Naver DataLab Trend API
    keywords: list of strings (up to 5)
    """
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    if client_id and client_secret:
        keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in keywords[:5]]
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": keyword_groups
        }

        # Attempt 1: NAVER API HUB DataLab
        try:
            hub_url = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
            hub_headers = {
                "X-NCP-APIGW-API-KEY-ID": client_id,
                "X-NCP-APIGW-API-KEY": client_secret,
                "Content-Type": "application/json"
            }
            res_hub = requests.post(hub_url, headers=hub_headers, json=body, timeout=8)
            if res_hub.status_code == 200:
                res_data = res_hub.json()
                res_data["source"] = "naver_api_hub"
                return res_data
        except Exception as e:
            print(f"NAVER API HUB DataLab error: {e}")

        # Attempt 2: Legacy Developers Center DataLab
        try:
            url = "https://openapi.naver.com/v1/datalab/search"
            headers = {
                "X-Naver-Client-Id": client_id,
                "X-Naver-Client-Secret": client_secret,
                "Content-Type": "application/json"
            }
            res = requests.post(url, headers=headers, json=body, timeout=8)
            if res.status_code == 200:
                res_data = res.json()
                res_data["source"] = "legacy_developer_center"
                return res_data
        except Exception as e:
            print(f"DataLab API error: {e}")

    return {
        "startDate": start_date, "endDate": end_date, "timeUnit": time_unit,
        "results": [], "source": "unavailable", "measurement_status": "unavailable"
    }
