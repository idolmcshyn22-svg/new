# fb_groups_scraper_focused.py - Focus on larger height element

import time, random, threading, re, requests, pandas as pd
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ----------------------------
# Helper utils
# ----------------------------

def parse_cookies_to_list(cookie_str):
    cookies_list = []
    for pair in cookie_str.split(';'):
        pair = pair.strip()
        if '=' in pair:
            name, value = pair.split('=', 1)
            cookies_list.append({'name': name.strip(), 'value': value.strip(), 'domain': '.facebook.com'})
    return cookies_list

def parse_cookies_to_dict(cookie_str):
    d = {}
    for pair in cookie_str.split(';'):
        pair = pair.strip()
        if '=' in pair:
            name, value = pair.split('=', 1)
            d[name.strip()] = value.strip()
    return d

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text.strip())
    ui_patterns = [
        r'\b(Like|Reply|Share|Comment|Translate|Hide|Report|Block)\b',
        r'\b(Thích|Trả lời|Chia sẻ|Bình luận|Dịch|Ẩn|Báo cáo|Chặn)\b',
        r'\b\d+\s*(min|minutes?|hours?|days?|seconds?|phút|giờ|ngày|giây)\s*(ago|trước)?\b',
        r'\b(Top fan|Most relevant|Newest|All comments|Bình luận hàng đầu)\b'
    ]
    for pattern in ui_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return text.strip()

def is_anonymous_user(username):
    """
    Kiểm tra xem có phải là người dùng ẩn danh không
    Args:
        username (str): Tên người dùng cần kiểm tra
    Returns:
        bool: True nếu là ẩn danh, False nếu không
    """
    if not username or username == "Unknown":
        return True
    
    username_lower = username.lower().strip()
    
    # Các pattern để nhận diện người dùng ẩn danh
    anonymous_patterns = [
        # Tiếng Việt
        r'\b(ẩn\s*danh|an\s*danh|người\s*dùng\s*ẩn\s*danh)\b',
        r'\b(thành\s*viên\s*ẩn\s*danh|tv\s*ẩn\s*danh)\b',
        r'\b(người\s*tham\s*gia\s*ẩn\s*danh|participant\s*ẩn\s*danh)\b',
        
        # Tiếng Anh  
        r'\b(anonymous|anon)\b',
        r'\b(anonymous\s*(user|member|participant))\b',
        r'\b(hidden\s*(user|member|participant))\b',
        r'\b(private\s*(user|member|participant))\b',
        
        # Các pattern phổ biến khác
        r'\b(user\s*\d+)\b',  # user123, user456
        r'\b(member\s*\d+)\b',  # member123
        r'\b(participant\s*\d+)\b',  # participant123
        r'\b(guest\s*\d*)\b',  # guest, guest123
        r'\b(unknown\s*(user|member))\b',
        r'^\d+$',  # Chỉ là số
        r'^[a-f0-9]{8,}$',  # Hash string dài
        
        # Facebook specific
        r'\b(facebook\s*user)\b',
        r'\b(fb\s*user)\b',
        r'\b(deleted\s*(user|account))\b',
        r'\b(deactivated\s*(user|account))\b',
    ]
    
    # Kiểm tra từng pattern
    for pattern in anonymous_patterns:
        if re.search(pattern, username_lower):
            print(f"    🚫 Detected anonymous user: '{username}' (matched: {pattern})")
            return True
    
    # Kiểm tra các trường hợp đặc biệt
    # Username quá ngắn (< 2 ký tự)
    if len(username.strip()) < 2:
        print(f"    🚫 Username too short: '{username}'")
        return True
    
    # Username chỉ chứa ký tự đặc biệt
    if re.match(r'^[^\w\s]+$', username):
        print(f"    🚫 Username only special chars: '{username}'")
        return True
    
    # Username có pattern nghi ngờ (nhiều số liên tiếp)
    if re.search(r'\d{6,}', username):
        print(f"    🚫 Username has suspicious number pattern: '{username}'")
        return True
    
    print(f"    ✅ Valid username: '{username}'")
    return False

def safe_get_element_text(element, max_retries=3):
    """
    Safely get text from element with retry mechanism for stale elements
    Args:
        element: Selenium WebElement
        max_retries (int): Maximum number of retries
    Returns:
        str: Element text or empty string if failed
    """
    for attempt in range(max_retries):
        try:
            return element.text.strip()
        except StaleElementReferenceException:
            print(f"    ⚠️ Stale element on attempt {attempt + 1}, retrying...")
            time.sleep(0.1)
            continue
        except Exception as e:
            print(f"    ⚠️ Error getting element text: {e}")
            return ""
    
    print(f"    ❌ Failed to get element text after {max_retries} attempts")
    return ""

def safe_get_element_attribute(element, attribute, max_retries=3):
    """
    Safely get attribute from element with retry mechanism for stale elements
    Args:
        element: Selenium WebElement
        attribute (str): Attribute name
        max_retries (int): Maximum number of retries
    Returns:
        str: Attribute value or empty string if failed
    """
    for attempt in range(max_retries):
        try:
            return element.get_attribute(attribute) or ""
        except StaleElementReferenceException:
            print(f"    ⚠️ Stale element on attempt {attempt + 1}, retrying...")
            time.sleep(0.1)
            continue
        except Exception as e:
            print(f"    ⚠️ Error getting element attribute: {e}")
            return ""
    
    print(f"    ❌ Failed to get element attribute after {max_retries} attempts")
    return ""

def safe_find_elements(element, by, value, max_retries=3):
    """
    Safely find elements with retry mechanism for stale elements
    Args:
        element: Selenium WebElement
        by: Locator strategy
        value: Locator value
        max_retries (int): Maximum number of retries
    Returns:
        list: List of WebElements or empty list if failed
    """
    for attempt in range(max_retries):
        try:
            return element.find_elements(by, value)
        except StaleElementReferenceException:
            print(f"    ⚠️ Stale element on attempt {attempt + 1}, retrying...")
            time.sleep(0.1)
            continue
        except Exception as e:
            print(f"    ⚠️ Error finding elements: {e}")
            return []
    
    print(f"    ❌ Failed to find elements after {max_retries} attempts")
    return []

def extract_uid_from_profile_url(profile_url):
    """
    Extract UID từ Facebook profile URL
    Args:
        profile_url (str): URL profile Facebook
    Returns:
        str: UID hoặc "Unknown"
    """
    if not profile_url:
        return "Unknown"
    
    try:
        # SUPER ENHANCED patterns để extract UID từ URL - bao gồm Facebook 2024 formats
        uid_patterns = [
            # Traditional formats
            r'profile\.php\?id=(\d+)',
            r'user\.php\?id=(\d+)', 
            r'/user/(\d+)',
            r'id=(\d+)',
            r'facebook\.com/profile\.php\?id=(\d+)',
            
            # New 2024 formats
            r'/people/[^/]+/(\d+)',  # facebook.com/people/name/123456
            r'facebook\.com/people/[^/]+/(\d+)',
            r'profile\.php\?id=(\d+)&',  # With additional params
            r'user\.php\?id=(\d+)&',  # With additional params
            r'fb://profile/(\d+)',  # Mobile app links
            r'fb://user/(\d+)',  # Mobile app links
            
            # Direct UID patterns (more flexible)
            r'facebook\.com/(\d{8,})',  # Giảm từ 10 xuống 8 digits
            r'/(\d{8,})(?:/|$|\?)',  # UID at end of path
            r'(\d{8,})'  # Any 8+ digit number (cuối cùng, rộng nhất)
        ]
        
        print(f"    🔍 Analyzing profile URL: {profile_url}")
        
        for i, pattern in enumerate(uid_patterns):
            match = re.search(pattern, profile_url)
            if match:
                uid = match.group(1)
                print(f"    📝 Pattern {i+1} matched: {pattern} -> UID: {uid}")
                if len(uid) >= 8:  # Giảm từ 10 xuống 8 để bao gồm nhiều UID hơn
                    print(f"    ✅ Valid UID extracted: {uid} (length: {len(uid)})")
                    return uid
                else:
                    print(f"    ⚠️ UID too short: {uid} (length: {len(uid)})")
        
        # Nếu URL có dạng facebook.com/username, thử extract username
        username_match = re.search(r'facebook\.com/([^/?]+)', profile_url)
        if username_match:
            username = username_match.group(1)
            if not username.isdigit() and len(username) > 2:
                print(f"    🔄 Found username in URL: {username}, will try to resolve to UID")
                return f"username:{username}"  # Đánh dấu để xử lý sau
        
        return "Unknown"
        
    except Exception as e:
        print(f"    ⚠️ Error extracting UID from URL: {e}")
        return "Unknown"

def get_uid_from_username(username, cookies_dict=None, driver=None, uid_cache=None):
    """
    SUPER OPTIMIZED: Lấy UID Facebook từ username với caching và performance improvements
    Args:
        username (str): Username Facebook
        cookies_dict (dict): Dictionary cookies để authenticate  
        driver: Selenium WebDriver instance (optional)
        uid_cache (dict): Cache dictionary để tránh resolve lại
    Returns:
        str: UID Facebook hoặc "Unknown" nếu không tìm thấy
    """
    if not username or username == "Unknown":
        return "Unknown"
    
    # CACHE CHECK: Kiểm tra cache trước
    if uid_cache and username in uid_cache:
        print(f"  ⚡ CACHE HIT: {username} -> {uid_cache[username]}")
        return uid_cache[username]
    
    try:
        # Chuẩn hóa username
        clean_username = username.strip()
        if clean_username.startswith('https://'):
            if 'facebook.com/' in clean_username:
                clean_username = clean_username.split('facebook.com/')[-1].split('?')[0].split('/')[0]
        
        print(f"  🔍 OPTIMIZED UID resolution for: {clean_username}")
        
        # OPTIMIZED Method 1: Sử dụng Selenium (nhưng nhanh hơn)
        if driver:
            try:
                print(f"    ⚡ Fast Selenium resolve...")
                
                profile_url = f"https://www.facebook.com/{clean_username}"
                current_url = driver.current_url
                
                # Navigate to profile với timeout ngắn hơn
                driver.get(profile_url)
                time.sleep(0.8)  # Tối ưu hóa thêm từ 1.5s xuống 0.8s
                
                final_url = driver.current_url
                print(f"    📍 Final URL: {final_url[:80]}...")
                
                # Extract UID from final URL
                uid_match = re.search(r'profile\.php\?id=(\d+)', final_url)
                if uid_match:
                    uid = uid_match.group(1)
                    print(f"    ✅ Fast UID via URL: {uid}")
                    
                    # Quick restore
                    driver.get(current_url)
                    time.sleep(0.1)  # Giảm từ 2s xuống 0.5s
                    return uid
                
                # ENHANCED page source scan với nhiều patterns hơn
                page_source = driver.page_source
                enhanced_patterns = [
                    r'"entity_id":"(\d+)"',
                    r'"userID":"(\d+)"',
                    r'"profile_id":"(\d+)"',
                    r'"profileId":"(\d+)"',
                    r'"actor_id":"(\d+)"',
                    r'"actorId":"(\d+)"',
                    r'"user_id":"(\d+)"',
                    r'"userId":"(\d+)"',
                    r'"fbid":"(\d+)"',
                    r'"id":"(\d+)"',
                    r'profileID&quot;:&quot;(\d+)&quot;',
                    r'profile_id&quot;:&quot;(\d+)&quot;',
                    r'"target_id":"(\d+)"',
                    r'"targetId":"(\d+)"'
                ]
                
                for pattern in enhanced_patterns:
                    matches = re.findall(pattern, page_source)
                    if matches:
                        for uid in matches:
                            if len(uid) >= 8:  # Giảm requirement từ 10 xuống 8
                                print(f"    ✅ Enhanced UID via source: {uid} (pattern: {pattern})")
                                # CACHE SAVE
                                if uid_cache is not None:
                                    uid_cache[clean_username] = uid
                                driver.get(current_url)
                                time.sleep(0.1)
                                return uid
                
                # Quick restore
                driver.get(current_url)
                time.sleep(0.1)
                
            except Exception as e:
                print(f"    ⚠️ Fast Selenium failed: {e}")
                try:
                    driver.get(current_url)
                    time.sleep(0.1)
                except:
                    pass
        
        # Method 2: Sử dụng requests (fallback)
        print(f"    🌐 Using requests to resolve UID...")
        
        # Tạo URL profile từ username
        profile_urls = [
            f"https://www.facebook.com/{clean_username}",
            f"https://m.facebook.com/{clean_username}",
            f"https://mbasic.facebook.com/{clean_username}"
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Thêm cookies nếu có
        if cookies_dict:
            cookie_string = '; '.join([f"{k}={v}" for k, v in cookies_dict.items()])
            headers['Cookie'] = cookie_string
        
        for url in profile_urls:
            try:
                print(f"    🔍 Trying to get UID from: {url}")
                
                response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
                
                if response.status_code == 200:
                    content = response.text
                    
                    # Tìm UID trong response
                    uid_patterns = [
                        r'"entity_id":"(\d+)"',
                        r'"userID":"(\d+)"',
                        r'"user_id":"(\d+)"',
                        r'"id":"(\d+)"',
                        r'profile\.php\?id=(\d+)',
                        r'user\.php\?id=(\d+)',
                        r'"profile_id":"(\d+)"',
                        r'entity_id=(\d+)',
                        r'profile_owner":"(\d+)"',
                        r'"pageID":"(\d+)"',
                        r'data-profileid="(\d+)"',
                        r'data-userid="(\d+)"',
                        r'"actorID":"(\d+)"',
                        r'"target_id":"(\d+)"'
                    ]
                    
                    for pattern in uid_patterns:
                        matches = re.findall(pattern, content)
                        if matches:
                            # Lấy UID đầu tiên tìm thấy (thường là UID chính xác nhất)
                            uid = matches[0]
                            # Validate UID (Facebook UID thường có ít nhất 10 chữ số)
                            if len(uid) >= 10 and uid.isdigit():
                                print(f"    ✅ Found UID: {uid} using pattern: {pattern}")
                                return uid
                    
                    # Fallback: tìm trong redirected URL
                    if 'profile.php?id=' in response.url:
                        uid_match = re.search(r'profile\.php\?id=(\d+)', response.url)
                        if uid_match:
                            uid = uid_match.group(1)
                            print(f"    ✅ Found UID from redirect URL: {uid}")
                            # CACHE SAVE: Lưu vào cache
                            if uid_cache is not None:
                                uid_cache[username] = uid
                            return uid
                
            except requests.RequestException as e:
                print(f"    ⚠️ Request failed for {url}: {e}")
                continue
            except Exception as e:
                print(f"    ⚠️ Error processing {url}: {e}")
                continue
        
        print(f"    ❌ Could not find UID for username: {username}")
        # CACHE SAVE: Lưu kết quả thất bại vào cache để tránh retry
        if uid_cache is not None:
            uid_cache[username] = "Unknown"
        return "Unknown"
        
    except Exception as e:
        print(f"❌ Error in get_uid_from_username: {e}")
        return "Unknown"

def get_uid_from_username_enhanced(username, cookies_dict=None, driver=None, uid_cache=None):
    """
    ENHANCED: Lấy UID từ username với nhiều phương pháp khác nhau
    """
    if not username or username == "Unknown":
        return "Unknown"
    
    # CACHE CHECK
    if uid_cache and username in uid_cache:
        print(f"  ⚡ CACHE HIT: {username} -> {uid_cache[username]}")
        return uid_cache[username]
    
    print(f"🔍 ENHANCED UID resolution for: {username}")
    
    try:
        # Method 1: Direct profile navigation với enhanced detection
        if driver:
            print(f"  🚀 Method 1: Direct profile navigation...")
            current_url = driver.current_url
            
            # Try multiple profile URL formats
            profile_urls = [
                f"https://www.facebook.com/{username}",
                f"https://m.facebook.com/{username}",
                f"https://facebook.com/{username}",
                f"https://www.facebook.com/profile.php?id={username}" if username.isdigit() else None
            ]
            
            for profile_url in profile_urls:
                if not profile_url:
                    continue
                    
                try:
                    print(f"    🔗 Trying: {profile_url}")
                    driver.get(profile_url)
                    time.sleep(1.2)  # Tăng thời gian chờ một chút để page load đầy đủ
                    
                    final_url = driver.current_url
                    print(f"    📍 Final URL: {final_url}")
                    
                    # Enhanced UID extraction từ final URL
                    uid_patterns = [
                        r'profile\.php\?id=(\d+)',
                        r'user\.php\?id=(\d+)',
                        r'/people/[^/]+/(\d+)',
                        r'facebook\.com/(\d{8,})',
                        r'(\d{8,})'
                    ]
                    
                    for pattern in uid_patterns:
                        match = re.search(pattern, final_url)
                        if match:
                            uid = match.group(1)
                            if len(uid) >= 8:
                                print(f"    ✅ UID from final URL: {uid}")
                                # CACHE SAVE
                                if uid_cache is not None:
                                    uid_cache[username] = uid
                                driver.get(current_url)
                                time.sleep(0.5)
                                return uid
                    
                    # Method 2: Enhanced page source scanning
                    print(f"    🔍 Scanning page source...")
                    page_source = driver.page_source
                    
                    # More comprehensive patterns
                    source_patterns = [
                        r'"entity_id":"(\d+)"',
                        r'"userID":"(\d+)"',
                        r'"profile_id":"(\d+)"',
                        r'"profileId":"(\d+)"',
                        r'"actor_id":"(\d+)"',
                        r'"actorId":"(\d+)"',
                        r'"user_id":"(\d+)"',
                        r'"userId":"(\d+)"',
                        r'"fbid":"(\d+)"',
                        r'"target_id":"(\d+)"',
                        r'"targetId":"(\d+)"',
                        r'profile_id&quot;:&quot;(\d+)&quot;',
                        r'entity_id&quot;:&quot;(\d+)&quot;',
                        r'data-profileid="(\d+)"',
                        r'data-uid="(\d+)"',
                        r'"id":"(\d+)","name":"' + re.escape(username),
                        r'"' + re.escape(username) + r'","id":"(\d+)"'
                    ]
                    
                    for pattern in source_patterns:
                        matches = re.findall(pattern, page_source, re.IGNORECASE)
                        if matches:
                            for uid in matches:
                                if len(uid) >= 8 and uid.isdigit():
                                    print(f"    ✅ UID from page source: {uid}")
                                    # CACHE SAVE
                                    if uid_cache is not None:
                                        uid_cache[username] = uid
                                    driver.get(current_url)
                                    time.sleep(0.5)
                                    return uid
                    
                except Exception as e:
                    print(f"    ⚠️ Profile URL failed: {e}")
                    continue
            
            # Restore original URL
            try:
                driver.get(current_url)
                time.sleep(0.5)
            except:
                pass
        
        # Method 3: Graph API approach (fallback)
        print(f"  🌐 Method 3: Graph API approach...")
        if cookies_dict:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Cookie': '; '.join([f"{k}={v}" for k, v in cookies_dict.items()])
            }
            
            # Try search API
            search_urls = [
                f"https://www.facebook.com/search/people/?q={username}",
                f"https://m.facebook.com/search/people/?q={username}"
            ]
            
            for search_url in search_urls:
                try:
                    response = requests.get(search_url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        # Look for profile links in search results
                        profile_links = re.findall(r'href="([^"]*profile\.php\?id=\d+[^"]*)"', response.text)
                        profile_links.extend(re.findall(r'href="([^"]*facebook\.com/\d{8,}[^"]*)"', response.text))
                        
                        for link in profile_links:
                            uid_match = re.search(r'(\d{8,})', link)
                            if uid_match:
                                uid = uid_match.group(1)
                                print(f"    ✅ UID from search: {uid}")
                                # CACHE SAVE
                                if uid_cache is not None:
                                    uid_cache[username] = uid
                                return uid
                
                except Exception as e:
                    print(f"    ⚠️ Search failed: {e}")
                    continue
        
        print(f"    ❌ Could not resolve UID for: {username}")
        # CACHE SAVE failure
        if uid_cache is not None:
            uid_cache[username] = "Unknown"
        return "Unknown"
        
    except Exception as e:
        print(f"❌ Error in enhanced UID resolution: {e}")
        return "Unknown"

# ----------------------------
# FOCUSED Facebook Groups Scraper
# ----------------------------

class FacebookGroupsScraper:
    def __init__(self, cookie_str, headless=True):
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Better user agent for modern Facebook
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.wait = WebDriverWait(self.driver, 15)
        self.cookie_str = cookie_str or ""
        self.cookies_list = parse_cookies_to_list(self.cookie_str)
        self.cookies_dict = parse_cookies_to_dict(self.cookie_str)
        self._stop_flag = False
        self.current_layout = None
        self._anonymous_filtered_count = 0
        
        # CACHE OPTIMIZATION: Thêm cache cho performance
        self._uid_cache = {}  # Cache UID resolution
        self._profile_cache = {}  # Cache profile data
        self._element_cache = {}  # Cache element data để tránh re-parse
        
        if self.cookies_list:
            self._login_with_cookies()

    def _login_with_cookies(self):
        # Start with regular Facebook for better groups access
        self.driver.get("https://www.facebook.com")
        time.sleep(1)
        
        for c in self.cookies_list:
            cookie = c.copy()
            cookie.pop('sameSite', None)
            cookie.pop('httpOnly', None) 
            cookie.pop('secure', None)
            cookie.setdefault('domain', '.facebook.com')
            try:
                self.driver.add_cookie(cookie)
            except: 
                pass
        
        self.driver.get("https://www.facebook.com")
        time.sleep(1.5)

    def load_post(self, post_url):
        print(f"Loading groups post: {post_url}")
        
        urls_to_try = []
        
        if "groups/" in post_url:
            # Try www first for groups, then mobile, then mbasic
            www_url = post_url.replace("mbasic.facebook.com", "www.facebook.com").replace("m.facebook.com", "www.facebook.com")
            mobile_url = post_url.replace("www.facebook.com", "m.facebook.com").replace("mbasic.facebook.com", "m.facebook.com")
            mbasic_url = post_url.replace("www.facebook.com", "mbasic.facebook.com").replace("m.facebook.com", "mbasic.facebook.com")
            
            urls_to_try = [www_url, mobile_url, mbasic_url]
        else:
            urls_to_try = [post_url]
        
        for url_attempt in urls_to_try:
            try:
                print(f"Trying URL: {url_attempt}")
                self.driver.get(url_attempt)
                time.sleep(6)
                
                current_url = self.driver.current_url
                page_title = self.driver.title
                
                print(f"Current URL: {current_url}")
                print(f"Page title: {page_title}")
                
                # Detect layout
                if "m.facebook.com" in current_url:
                    self.current_layout = "mobile"
                elif "mbasic.facebook.com" in current_url:
                    self.current_layout = "mbasic"
                else:
                    self.current_layout = "www"
                
                print(f"Detected layout: {self.current_layout}")
                
                # Check login status
                if any(keyword in page_title.lower() for keyword in ["log in", "login", "đăng nhập"]):
                    print("❌ Not logged in with this URL, trying next...")
                    continue
                
                print(f"✅ Successfully loaded groups post with {self.current_layout} layout")
                
                # Try to switch to "All comments" view
                self._switch_to_all_comments()

                # Try to click "View more comments" button
                self._click_view_more()
                
                return True
                    
            except Exception as e:
                print(f"Failed to load {url_attempt}: {e}")
                continue
        
        print("❌ Failed to load post with any URL variant")
        return False

    def clear_page_cache(self):
        """Clear page cache and force reload to ensure fresh DOM"""
        try:
            print("🧹 Clearing page cache...")
            
            # Clear browser cache
            self.driver.execute_script("window.localStorage.clear();")
            self.driver.execute_script("window.sessionStorage.clear();")
            
            # Force page refresh
            self.driver.refresh()
            time.sleep(2)  # Wait for fresh load
            
            print("✅ Page cache cleared and refreshed")
            
        except Exception as e:
            print(f"⚠️ Error clearing cache: {e}")

    def _switch_to_all_comments(self):
        """Switch to 'All comments' view to get more comments"""
        print("🔄 Attempting to switch to 'All comments' view...")
        
        try:
            time.sleep(1)
            
            # Enhanced selectors for all comments button
            all_comments_selectors = [
                # Vietnamese selectors
                "//span[contains(text(),'Tất cả bình luận')]",
                "//div[contains(text(),'Tất cả bình luận')]",
                "//a[contains(text(),'Tất cả bình luận')]",
                "//button[contains(text(),'Tất cả bình luận')]",
                
                # English selectors
                "//span[contains(text(),'All comments')]",
                "//div[contains(text(),'All comments')]",
                "//a[contains(text(),'All comments')]",
                "//button[contains(text(),'All comments')]",
                
                # Role-based selectors
                "//div[@role='button' and (contains(text(),'Tất cả') or contains(text(),'All'))]",
                "//span[@role='button' and (contains(text(),'Tất cả') or contains(text(),'All'))]",
                
                # Aria-label selectors
                "//div[contains(@aria-label,'comment') and contains(text(),'All')]",
                "//div[contains(@aria-label,'bình luận') and contains(text(),'Tất cả')]"
            ]
            
            clicked = False
            self.all_comments_button = None  # Store the button for later use
            
            for selector in all_comments_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            print(f"  Found 'All comments' button: {element.text}")
                            
                            # Store the button for later use
                            self.all_comments_button = element
                            
                            # Scroll into view
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                            time.sleep(1)
                            
                            # Try to click
                            try:
                                element.click()
                                clicked = True
                                print("  ✅ Successfully clicked 'All comments' button")
                                time.sleep(1.5)  # Wait for comments to load
                                break
                            except:
                                # Try JavaScript click
                                try:
                                    self.driver.execute_script("arguments[0].click();", element)
                                    clicked = True
                                    print("  ✅ Successfully clicked 'All comments' button (JS)")
                                except:
                                    continue

                            # Click on div with role="menuitem" and tabindex="0"
                            try:
                                menuitem_element = self.driver.find_element(By.XPATH, "//div[@role='menuitem' and @tabindex='0']")
                                self.driver.execute_script("arguments[0].click();", menuitem_element)
                                print("  ✅ Successfully clicked menuitem div")
                                time.sleep(2)  # Wait for any menu actions to complete
                            except Exception as e:
                                print(f"  ⚠️ Could not find or click menuitem div: {e}")
                            
                            time.sleep(1.5)
                            break
                    
                    if clicked:
                        break
                        
                except Exception as e:
                    continue
            
            if not clicked:
                print("  ⚠️ Could not find or click 'All comments' button, proceeding with current view")
            else:
                print("  🎯 Switched to 'All comments' view successfully")
                
        except Exception as e:
            print(f"  ⚠️ Error switching to 'All comments' view: {e}")
            print("  Proceeding with current view...")

    def _click_view_more(self):
        """Click on 'View more comments' button to load more comments"""
        print("🔄 Attempting to click 'View more comments' button...")
        
        try:
            time.sleep(1)
            
            # Enhanced selectors for view more button
            view_more_selectors = [
                "//div[contains(text(),'View more comments')]",
                "//button[contains(text(),'View more comments')]",
                "//a[contains(text(),'View more comments')]",
                "//span[contains(text(),'View more comments')]"
            ]

            clicked = False
            for selector in view_more_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            print(f"  Found 'View more comments' button: {element.text}")
                            
                            # Scroll into view
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                            time.sleep(1)
                            
                            # Try to click
                            try:
                                element.click()
                                clicked = True
                                print("  ✅ Successfully clicked 'View more comments' button")
                                time.sleep(1.5)  # Wait for comments to load
                                break
                            except:
                                # Try JavaScript click
                                try:
                                    self.driver.execute_script("arguments[0].click();", element)
                                    clicked = True
                                    print("  ✅ Successfully clicked 'View more comments' button (JS)")
                                    
                                    time.sleep(1.5)
                                    break
                                except:
                                    continue
                    
                    if clicked:
                        break
                        
                except Exception as e:
                    continue
            
            if not clicked:
                print("  ⚠️ Could not find or click 'View more comments' button, proceeding with current view")
            else:
                print("  🎯 Switched to 'View more comments' view successfully")
                
        except Exception as e:
            print(f"  ⚠️ Error switching to 'View more comments' view: {e}")
            print("  Proceeding with current view...")

    def refresh_stale_elements(self, elements_list):
        """
        Refresh stale elements by re-finding them
        Args:
            elements_list (list): List of potentially stale elements
        Returns:
            list: List of refreshed elements
        """
        print("🔄 Refreshing potentially stale elements...")
        refreshed_elements = []
        
        for i, element in enumerate(elements_list):
            try:
                # Test if element is stale
                _ = element.tag_name
                refreshed_elements.append(element)
            except StaleElementReferenceException:
                print(f"  ⚠️ Element {i+1} is stale, attempting to refresh...")
                try:
                    # Try to re-find element by its position and attributes
                    location = element.location
                    size = element.size
                    
                    # Find elements near the same location
                    nearby_elements = self.driver.find_elements(By.XPATH, "//*")
                    
                    for candidate in nearby_elements:
                        try:
                            candidate_location = candidate.location
                            candidate_size = candidate.size
                            
                            # Check if location and size match approximately
                            if (abs(candidate_location['x'] - location['x']) < 10 and
                                abs(candidate_location['y'] - location['y']) < 10 and
                                abs(candidate_size['width'] - size['width']) < 50 and
                                abs(candidate_size['height'] - size['height']) < 50):
                                
                                refreshed_elements.append(candidate)
                                print(f"    ✅ Refreshed element {i+1}")
                                break
                        except:
                            continue
                    else:
                        print(f"    ❌ Could not refresh element {i+1}")
                        
                except Exception as refresh_error:
                    print(f"    ❌ Error refreshing element {i+1}: {refresh_error}")
            except Exception as e:
                print(f"  ⚠️ Error checking element {i+1}: {e}")
                continue
        
        print(f"✅ Refreshed {len(refreshed_elements)}/{len(elements_list)} elements")
        return refreshed_elements

    def extract_with_retry(self, element, index, max_retries=2):
        """
        Extract comment data with retry mechanism for stale elements
        Args:
            element: Selenium WebElement
            index (int): Element index
            max_retries (int): Maximum retry attempts
        Returns:
            dict or None: Comment data or None if failed
        """
        for attempt in range(max_retries + 1):
            try:
                return self.extract_comment_data_focused(element, index)
            except StaleElementReferenceException:
                if attempt < max_retries:
                    print(f"    ⚠️ Stale element on attempt {attempt + 1}, retrying after refresh...")
                    time.sleep(1)
                    # Try to refresh page partially
                    try:
                        self.driver.execute_script("window.scrollBy(0, -100);")
                        time.sleep(0.1)
                        self.driver.execute_script("window.scrollBy(0, 100);")
                        time.sleep(0.1)
                    except:
                        pass
                    continue
                else:
                    print(f"    ❌ Element still stale after {max_retries} retries, skipping...")
                    return None
            except Exception as e:
                print(f"    ⚠️ Non-stale error on attempt {attempt + 1}: {e}")
                if attempt < max_retries:
                    time.sleep(0.1)
                    continue
                else:
                    return None
        
        return None

    def extract_fresh_comments_from_container(self, container_element):
        """
        Extract fresh comment elements from container to avoid stale references
        Args:
            container_element: Parent container element
        Returns:
            list: Fresh comment elements
        """
        print("🔄 Extracting fresh comment elements from container...")
        fresh_elements = []
        
        try:
            # Strategy 1: Find all divs in container and filter for comments
            all_divs = container_element.find_elements(By.XPATH, ".//div")
            print(f"  Found {len(all_divs)} total divs in container")
            
            comment_count = 0
            for div in all_divs:
                try:
                    if self.is_comment_div(div):
                        fresh_elements.append(div)
                        comment_count += 1
                        
                        # Log every 10th comment for progress
                        if comment_count % 10 == 0:
                            print(f"    ✅ Found {comment_count} comment divs so far...")
                            
                except StaleElementReferenceException:
                    print(f"    ⚠️ Div became stale during check, skipping...")
                    continue
                except Exception as e:
                    continue
            
            print(f"✅ Extracted {len(fresh_elements)} fresh comment elements")
            return fresh_elements
            
        except Exception as e:
            print(f"⚠️ Error extracting fresh elements: {e}")
            return []

    def extract_all_fresh_comments(self):
        """
        Extract all fresh comments from current page state
        Returns:
            list: Fresh comment elements
        """
        print("🔄 Extracting ALL fresh comments from current page...")
        fresh_elements = []
        
        try:
            # ENHANCED Strategy: Comprehensive selectors để không bỏ sót comments
            comment_selectors = []
            
            # Universal selectors (work across all layouts)
            universal_selectors = [
                # Data-based
                "//div[contains(@data-testid, 'comment')]",
                "//div[contains(@data-testid, 'UFI2Comment')]",
                "//div[contains(@class, 'comment')]",
                "//div[contains(@class, 'UFIComment')]",
                "//div[contains(@data-ft, 'comment')]",
                "//div[contains(@id, 'comment_')]",
                
                # Profile link based (most reliable)
                "//div[.//a[contains(@href, 'facebook.com/profile.php?id=')]]",
                "//div[.//a[contains(@href, 'facebook.com/user.php?id=')]]",
                "//div[.//a[contains(@href, 'facebook.com/people/')]]",
                
                # Content-based
                "//div[string-length(normalize-space(text())) > 15 and .//a[contains(@href, 'facebook.com')]]",
                
                # Structure-based
                "//div[contains(@class, 'userContentWrapper')]",
                "//div[contains(@class, 'UFIContainer')]"
            ]
            
            if self.current_layout == "www":
                comment_selectors = universal_selectors + [
                    "//div[@role='article']",
                    "//div[contains(@aria-label, 'Comment by')]",
                    "//div[contains(@aria-label, 'Bình luận của')]",
                    "//div[.//a[contains(@href, 'facebook.com/') and not(contains(@href, 'groups/') or contains(@href, 'pages/') or contains(@href, 'events/'))]]"
                ]
            elif self.current_layout == "mobile":
                comment_selectors = universal_selectors + [
                    "//div[@data-sigil='comment']",
                    "//div[.//a[contains(@href, 'profile.php') or contains(@href, 'user.php')]]"
                ]
            else:  # mbasic
                comment_selectors = universal_selectors + [
                    "//div[@data-ft and contains(@data-ft, 'comment')]"
                ]
            
            # Extract using each selector
            for i, selector in enumerate(comment_selectors):
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    print(f"  Selector {i+1}: Found {len(elements)} elements")
                    
                    for elem in elements:
                        try:
                            # Quick validation
                            text = safe_get_element_text(elem)
                            if len(text) > 10 and elem not in fresh_elements:
                                fresh_elements.append(elem)
                        except:
                            continue
                            
                except Exception as e:
                    print(f"  Selector {i+1} failed: {e}")
                    continue
            
            # Remove duplicates and sort by position
            unique_elements = []
            seen_locations = set()
            
            for elem in fresh_elements:
                try:
                    location = elem.location
                    location_key = f"{location['x']}_{location['y']}"
                    
                    if location_key not in seen_locations:
                        unique_elements.append(elem)
                        seen_locations.add(location_key)
                        
                except:
                    continue
            
            # Sort by position (top to bottom)
            try:
                unique_elements.sort(key=lambda x: (x.location['y'], x.location['x']))
            except:
                pass
            
            print(f"✅ Final fresh elements: {len(unique_elements)} unique comments")
            return unique_elements
            
        except Exception as e:
            print(f"⚠️ Error in extract_all_fresh_comments: {e}")
            return []

    def is_comment_div(self, div_element):
        """Check if a div element contains comment-like content with stale element protection"""
        try:
            # Get text content safely
            text = safe_get_element_text(div_element)
            if len(text) < 10:  # Too short to be a meaningful comment
                return False
            
            # Check for profile links (common in comments) safely
            profile_links = safe_find_elements(div_element, By.XPATH, ".//a[contains(@href, 'profile') or contains(@href, 'user') or contains(@href, 'facebook.com/')]")
            if profile_links:
                return True
            
            # Check for comment-specific attributes safely
            aria_label = safe_get_element_attribute(div_element, 'aria-label')
            if 'comment' in aria_label.lower() or 'bình luận' in aria_label.lower():
                return True
            
            # Check for comment-specific classes safely
            class_attr = safe_get_element_attribute(div_element, 'class')
            if any(keyword in class_attr.lower() for keyword in ['comment', 'reply', 'response']):
                return True
            
            # Check for comment-specific data attributes safely
            data_ft = safe_get_element_attribute(div_element, 'data-ft')
            if 'comment' in data_ft.lower():
                return True
            
            # Check for role attribute safely
            role = safe_get_element_attribute(div_element, 'role')
            if role == 'article':
                return True
            
            # Check for comment ID patterns safely
            element_id = safe_get_element_attribute(div_element, 'id')
            if 'comment' in element_id.lower():
                return True
            
            # Check for time elements (comments often have timestamps) safely
            time_elements = safe_find_elements(div_element, By.XPATH, ".//time | .//span[contains(@class, 'time')] | .//a[contains(@class, 'time')]")
            if time_elements:
                return True
            
            # Check for like/reply buttons (common in comments) safely
            action_buttons = safe_find_elements(div_element, By.XPATH, ".//*[contains(text(), 'Like') or contains(text(), 'Reply') or contains(text(), 'Thích') or contains(text(), 'Trả lời')]")
            if action_buttons:
                return True
            
            # Check for reasonable text length and structure
            if len(text) > 20 and ('@' in text or '.' in text or '!' in text or '?' in text):
                return True
            
            return False
            
        except Exception as e:
            print(f"Error checking if div is comment: {e}")
            return False

    def extract_groups_comments(self):
        """FOCUSED comment extraction với immediate processing để tránh stale elements"""
        print(f"=== EXTRACTING GROUPS COMMENTS (FOCUSED + IMMEDIATE) ===")
        
        # Initialize results
        all_comments_data = []
        seen_content = set()

        # Find "All comments" button's parent with class html-div
        try:
            # Use the all_comments_button from _switch_to_all_comments if available
            all_comments_button = getattr(self, 'all_comments_button', None)
            
            if not all_comments_button:
                print("⚠️ No 'All comments' button found from previous method, searching again...")
                # Look for "All comments" button with various possible text variations
                all_comments_selectors = [
                    "//button[contains(text(), 'All comments')]",
                    "//a[contains(text(), 'All comments')]",
                    "//span[contains(text(), 'All comments')]",
                    "//div[contains(text(), 'All comments')]",
                    "//*[contains(text(), 'View all comments')]",
                    "//*[contains(text(), 'See all comments')]",
                    "//*[contains(text(), 'Show all comments')]"
                ]
                
                for selector in all_comments_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        if elements:
                            all_comments_button = elements[0]
                            print(f"✅ Found 'All comments' button using selector: {selector}")
                            break
                    except Exception as e:
                        continue
            else:
                print("✅ Using 'All comments' button from _switch_to_all_comments method")
            
            if all_comments_button:
                # Find the parent with class html-div
                parent_with_html_div = None
                
                # Method 1: Get the closest parent with class containing 'html-div'
                try:
                    closest_parent = all_comments_button.find_element(By.XPATH, "ancestor::*[contains(@class, 'html-div')][1]")
                    if closest_parent:
                        parent_with_html_div = closest_parent
                        print("✅ Found closest parent with html-div class")
                except:
                    pass
                
                # Method 2: Look for immediate parent with class containing 'html-div' (fallback)
                if not parent_with_html_div:
                    try:
                        parent = all_comments_button.find_element(By.XPATH, "./..")
                        if 'html-div' in parent.get_attribute('class') or 'html-div' in parent.get_attribute('className'):
                            parent_with_html_div = parent
                            print("✅ Found parent with html-div class (immediate parent)")
                    except:
                        pass
                
                # Method 3: Look for any ancestor with class containing 'html-div' (fallback)
                if not parent_with_html_div:
                    try:
                        ancestors = all_comments_button.find_elements(By.XPATH, "ancestor::*[contains(@class, 'html-div')]")
                        if ancestors:
                            parent_with_html_div = ancestors[0]
                            print("✅ Found parent with html-div class (ancestor)")
                    except:
                        pass
                
                # Method 4: Look for any div with class containing 'html-div' that contains the button (fallback)
                if not parent_with_html_div:
                    try:
                        # More efficient: search only in the document body
                        html_div_containers = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'html-div')]")
                        for container in html_div_containers:
                            try:
                                # Check if the button is a descendant of this container
                                if container.find_element(By.XPATH, f".//*[contains(@text, '{all_comments_button.text}') or contains(@aria-label, '{all_comments_button.text}')]"):
                                    parent_with_html_div = container
                                    print("✅ Found parent with html-div class (container fallback)")
                                    break
                            except:
                                continue
                    except:
                        pass
                
                if parent_with_html_div:
                    print(f"✅ Successfully found 'All comments' button's parent with html-div class")
                    print(f"   Parent tag: {parent_with_html_div.tag_name}")
                    print(f"   Parent class: {parent_with_html_div.get_attribute('class')}")
                    
                    # Get comment parent divs that come after the "All comments" parent_with_html_div
                    print("🔍 Searching for comment parent divs after 'All comments' parent...")
                    
                    comment_parent_divs = []
                    
                    # Method 1: Find the next div that comes immediately after the parent_with_html_div
                    try:
                        # Get only the next div that is a sibling of the parent_with_html_div
                        next_div = parent_with_html_div.find_element(By.XPATH, "./following-sibling::div[1]")
                        print(f"Found next div after parent_with_html_div")
                        print(f"Next div class: {next_div.get_attribute('class')}")
                        
                        # OPTIMIZED click loop với performance improvements
                        print("🚀 Starting optimized 'View more comments' click loop...")
                        previous_comment_count = 0
                        no_new_comments_count = 0
                        max_no_new_comments = 1  # Tối ưu hóa: giảm từ 2 xuống 1
                        max_click_rounds = 5  # Tối ưu hóa: giảm từ 10 xuống 5 rounds
                        click_round = 0
                        
                        while no_new_comments_count < max_no_new_comments and click_round < max_click_rounds:
                            click_round += 1
                            print(f"\n--- Click Round {click_round}/{max_click_rounds} ---")
                            
                            # Look for "View more comments" button
                            view_more_selectors = [
                                "//button[contains(text(), 'View more comments')]",
                                "//a[contains(text(), 'View more comments')]",
                                "//span[contains(text(), 'View more comments')]",
                                "//div[contains(text(), 'View more comments')]",
                                "//*[contains(text(), 'View more')]",
                                "//*[contains(text(), 'Show more comments')]",
                                "//*[contains(text(), 'Load more comments')]",
                                "//*[contains(text(), 'See more comments')]"
                            ]
                            
                            view_more_button = None
                            for selector in view_more_selectors:
                                try:
                                    elements = self.driver.find_elements(By.XPATH, selector)
                                    if elements:
                                        view_more_button = elements[0]
                                        print(f"✅ Found 'View more comments' button using selector: {selector}")
                                        break
                                except Exception as e:
                                    continue
                            
                            if view_more_button:
                                try:
                                    self.driver.execute_script("arguments[0].click();", view_more_button)
                                    print("🖱️ Clicked 'View more comments' button")
                                except Exception as e:
                                    print(f"⚠️ Error clicking 'View more comments' button: {e}")
                                    break
                            else:
                                print("⚠️ No 'View more comments' button found")
                                no_new_comments_count += 1
                                print(f"⚠️ No new comments button detected ({no_new_comments_count}/{max_no_new_comments})")
                                break
                            
                            # Wait for new comments to load (optimized)
                            print("⏳ Waiting 1 second for new comments to load...")
                            time.sleep(1)  # Tối ưu hóa: giảm từ 3s xuống 1s
                            
                            # RE-FIND fresh container và extract immediately
                            processed_in_this_round = 0
                            current_comment_divs = []
                            
                            try:
                                # Re-find parent và next_div để tránh stale
                                fresh_parent = self.driver.find_element(By.XPATH, "//*[contains(@class, 'html-div')]")
                                fresh_next_div = fresh_parent.find_element(By.XPATH, "./following-sibling::div[1]")
                                fresh_children = fresh_next_div.find_elements(By.XPATH, "./div")
                                
                                print(f"🔄 Re-found fresh container with {len(fresh_children)} children")
                                
                                # BATCH PROCESSING: Xử lý nhiều comments cùng lúc
                                batch_size = 20  # Xử lý 20 comments mỗi batch
                                comment_children = [child for child in fresh_children if self.is_comment_div(child)]
                                
                                print(f"🚀 BATCH processing {len(comment_children)} comment divs in batches of {batch_size}")
                                
                                for batch_start in range(0, len(comment_children), batch_size):
                                    batch_end = min(batch_start + batch_size, len(comment_children))
                                    batch_children = comment_children[batch_start:batch_end]
                                    
                                    print(f"  📦 Processing batch {batch_start//batch_size + 1}: {len(batch_children)} comments")
                                    
                                    for child_index, child in enumerate(batch_children):
                                        try:
                                            # FAST extraction (skip UID resolution trong immediate processing)
                                            comment_data = self.extract_comment_data_fast(child, len(all_comments_data))
                                            
                                            if comment_data:
                                                # Check anonymous và duplicates ngay
                                                if comment_data['Name'] != "Unknown" and not is_anonymous_user(comment_data['Name']):
                                                    content_signature = f"{comment_data['Name']}_{comment_data['ProfileLink']}"
                                                    if content_signature not in seen_content:
                                                        seen_content.add(content_signature)
                                                        comment_data['Type'] = 'Comment'
                                                        comment_data['Layout'] = self.current_layout
                                                        comment_data['Source'] = f'Batch Round {click_round}'
                                                        all_comments_data.append(comment_data)
                                                        processed_in_this_round += 1
                                                    else:
                                                        print(f"✗ BATCH: Duplicate {comment_data['Name']}")
                                                else:
                                                    if comment_data['Name'] != "Unknown" and is_anonymous_user(comment_data['Name']):
                                                        self._anonymous_filtered_count += 1
                                            
                                            current_comment_divs.append(child)
                                            
                                        except Exception as extract_error:
                                            print(f"⚠️ BATCH extraction error: {extract_error}")
                                            current_comment_divs.append(child)
                                            continue
                                    
                                    # Progress update per batch
                                    if processed_in_this_round > 0:
                                        print(f"  ✅ Batch {batch_start//batch_size + 1}: +{len([c for c in all_comments_data[-processed_in_this_round:] if c['Source'] == f'Batch Round {click_round}'])} new comments")
                                
                            except Exception as container_error:
                                print(f"⚠️ Error re-finding fresh container: {container_error}")
                                # Fallback: try global extraction for this round
                                try:
                                    global_elements = self.extract_all_fresh_comments()
                                    print(f"🔄 Fallback: Found {len(global_elements)} global elements")
                                    
                                    for elem in global_elements[-10:]:  # Process last 10 (likely new ones)
                                        try:
                                            comment_data = self.extract_comment_data_fast(elem, len(all_comments_data))
                                            if comment_data and comment_data['Name'] != "Unknown":
                                                if not is_anonymous_user(comment_data['Name']):
                                                    content_signature = f"{comment_data['Name']}_{comment_data['ProfileLink']}"
                                                    if content_signature not in seen_content:
                                                        seen_content.add(content_signature)
                                                        comment_data['Source'] = f'Global Fallback Round {click_round}'
                                                        all_comments_data.append(comment_data)
                                                        processed_in_this_round += 1
                                                        print(f"✅ FALLBACK: Added {comment_data['Name']}")
                                                else:
                                                    self._anonymous_filtered_count += 1
                                        except:
                                            continue
                                    
                                except Exception as global_error:
                                    print(f"⚠️ Global fallback also failed: {global_error}")
                                    break
                            
                            current_comment_count = len(current_comment_divs)
                            print(f"📊 Round {click_round}: {current_comment_count} divs found")
                            print(f"✅ Processed {processed_in_this_round} new comments in this round")
                            print(f"📊 Total processed so far: {len(all_comments_data)} comments")
                            
                            # Check progress
                            if processed_in_this_round > 0:
                                print(f"✅ Progress made in round {click_round}!")
                                no_new_comments_count = 0  # Reset counter
                            else:
                                no_new_comments_count += 1
                                print(f"⚠️ No progress in round {click_round} ({no_new_comments_count}/{max_no_new_comments})")
                            
                            # EARLY EXIT: Dynamic based on performance - Tối ưu hóa cho 1k comments
                            early_exit_threshold = 200 if click_round > 3 else 500  # Tăng threshold để lấy nhiều comment hơn
                            if len(all_comments_data) >= early_exit_threshold:
                                print(f"🎯 Early exit: Đã có {len(all_comments_data)} comments (threshold: {early_exit_threshold})")
                                break
                            
                            # Check for stop flag
                            if self._stop_flag:
                                print("⏹️ Stop flag detected, breaking click loop")
                                break
                        
                        print(f"🏁 Click loop completed. Final comment count: {current_comment_count}")
                        print(f"📊 IMMEDIATE processing results: {len(all_comments_data)} comments extracted during clicks")
                        
                        # Return immediate results (đã được process trong loop)
                        if len(all_comments_data) > 0:
                            print(f"\n=== IMMEDIATE EXTRACTION COMPLETE: {len(all_comments_data)} comments ===")
                            return all_comments_data
                        
                        # FALLBACK: Nếu immediate processing không có kết quả, thử fresh extraction
                        print("⚠️ No results from immediate processing, trying fresh extraction...")
                        fresh_comment_elements = self.extract_all_fresh_comments()

                        if len(fresh_comment_elements) > 0:
                            print(f"🎯 Processing {len(fresh_comment_elements)} fresh comment elements")
                            # Extract comment data from the fresh elements
                            comments_data = []
                            fresh_seen_content = set()
                            
                            for i, element in enumerate(fresh_comment_elements):
                                if self._stop_flag:
                                    break
                                    
                                try:
                                    print(f"\n--- Processing fresh comment element {i+1}/{len(fresh_comment_elements)} ---")
                                    
                                    comment_data = self.extract_comment_data_focused(element, i)
                                    
                                    if not comment_data:
                                        continue
                                    
                                    # Deduplication + Anonymous filter
                                    if comment_data['Name'] == "Unknown":
                                        print("  ✗ Skipped: no username found")
                                        continue
                                    
                                    # 🚫 BỎ QUA NGƯỜI DÙNG ẨN DANH
                                    if is_anonymous_user(comment_data['Name']):
                                        print(f"  🚫 Skipped anonymous user: {comment_data['Name']}")
                                        self._anonymous_filtered_count += 1
                                        continue
                                        
                                    # Check for duplicates
                                    content_signature = f"{comment_data['Name']}_{comment_data['ProfileLink']}"
                                    if content_signature in fresh_seen_content:
                                        print("  ✗ Skipped: duplicate user")
                                        continue
                                    fresh_seen_content.add(content_signature)
                                    
                                    comment_data['Type'] = 'Comment'
                                    comment_data['Layout'] = self.current_layout
                                    comment_data['Source'] = 'Fresh Extraction Fallback'
                                    
                                    comments_data.append(comment_data)
                                    print(f"  ✅ Added: {comment_data['Name']} - Profile: {comment_data['ProfileLink'][:50]}...")
                                    
                                except Exception as e:
                                    print(f"  Error processing fresh element {i}: {e}")
                                    continue
                            
                            print(f"\n=== FRESH FALLBACK EXTRACTION COMPLETE: {len(comments_data)} comments ===")
                            return comments_data
                            
                    except Exception as e:
                        print(f"Error finding next div: {e}")
                    
                    print(f"🎯 Total comment parent divs found after 'All comments': {len(comment_parent_divs)}")
                    # Extract comment data from the found divs
                    comments_data = []
                    seen_content = set()
                    
                    for i, element in enumerate(comment_parent_divs):
                        if self._stop_flag:
                            break
                            
                        try:
                            print(f"\n--- Processing comment div {i+1}/{len(comment_parent_divs)} ---")
                            
                            comment_data = self.extract_with_retry(element, i)
                            
                            if not comment_data:
                                continue
                            
                            # Deduplication + Anonymous filter
                            if comment_data['Name'] == "Unknown":
                                print("  ✗ Skipped: no username found")
                                continue
                            
                            # 🚫 BỎ QUA NGƯỜI DÙNG ẨN DANH
                            if is_anonymous_user(comment_data['Name']):
                                print(f"  🚫 Skipped anonymous user: {comment_data['Name']}")
                                self._anonymous_filtered_count += 1
                                continue
                                
                            # Check for duplicates
                            content_signature = f"{comment_data['Name']}_{comment_data['ProfileLink']}"
                            if content_signature in seen_content:
                                print("  ✗ Skipped: duplicate user")
                                continue
                            seen_content.add(content_signature)
                            
                            comment_data['Type'] = 'Comment'
                            comment_data['Layout'] = self.current_layout
                            comment_data['Source'] = 'All Comments Container'
                            
                            comments_data.append(comment_data)
                            print(f"  ✅ Added: {comment_data['Name']} - Profile: {comment_data['ProfileLink'][:50]}...")
                            
                        except Exception as e:
                            print(f"  Error processing comment div {i}: {e}")
                            continue
                    
                    print(f"\n=== EXTRACTION COMPLETE: {len(comments_data)} comments ===")
                    return comments_data
                else:
                    print("❌ Could not find parent with html-div class for 'All comments' button")
                    
            else:
                print("❌ Could not find 'All comments' button")
                
        except Exception as e:
            print(f"❌ Error while searching for 'All comments' button's parent: {e}")
        
        # Save page for debugging
        try:
            with open(f"debug_focused_{self.current_layout}.html", "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            print(f"Saved page to debug_focused_{self.current_layout}.html")
        except:
            pass
        
        # FALLBACK: Use fresh extraction if no comments found above
        print("🔄 Using fresh extraction strategy to avoid stale elements...")
        
        # Extract all fresh comments from current page
        all_comment_elements = self.extract_all_fresh_comments()
        
        if len(all_comment_elements) == 0:
            print("⚠️ No comments found with fresh extraction, trying fallback selectors...")
            
            fallback_selectors = [
                "//div[.//a[contains(@href, 'facebook.com/')] and string-length(normalize-space(text())) > 20]",
                "//div[string-length(normalize-space(text())) > 30]",
                "//*[.//a[contains(@href, 'profile')] and string-length(normalize-space(text())) > 15]"
            ]
            
            for selector in fallback_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    print(f"Fallback selector: Found {len(elements)} elements")
                    for elem in elements:
                        try:
                            text = safe_get_element_text(elem)
                            if len(text) > 10 and elem not in all_comment_elements:
                                all_comment_elements.append(elem)
                        except:
                            continue
                    
                    if len(all_comment_elements) > 20:
                        break
                except:
                    continue
        
        comments = []
        seen_content = set()
        
        print(f"Processing {len(all_comment_elements)} fresh comment elements...")
        
        # Process each fresh element
        for i, element in enumerate(all_comment_elements):
            if self._stop_flag:
                break
                
            try:
                print(f"\n--- Fresh Element {i+1}/{len(all_comment_elements)} ---")
                
                comment_data = self.extract_comment_data_focused(element, i)
                
                if not comment_data:
                    continue
                
                # Deduplication + Anonymous filter
                if comment_data['Name'] == "Unknown":
                    print("  ✗ Skipped: no username found")
                    continue
                
                # 🚫 BỎ QUA NGƯỜI DÙNG ẨN DANH
                if is_anonymous_user(comment_data['Name']):
                    print(f"  🚫 Skipped anonymous user: {comment_data['Name']}")
                    self._anonymous_filtered_count += 1
                    continue
                    
                # Check for duplicates
                content_signature = f"{comment_data['Name']}_{comment_data['ProfileLink']}"
                if content_signature in seen_content:
                    print("  ✗ Skipped: duplicate user")
                    continue
                seen_content.add(content_signature)
                
                comment_data['Type'] = 'Comment'
                comment_data['Layout'] = self.current_layout
                comment_data['Source'] = 'Fresh Extraction (STALE-FREE)'
                
                comments.append(comment_data)
                print(f"  ✅ Added: {comment_data['Name']} - Profile: {comment_data['ProfileLink'][:50]}...")
                
            except StaleElementReferenceException:
                print(f"  ⚠️ Element {i+1} became stale during processing, skipping...")
                continue
            except Exception as e:
                print(f"  ⚠️ Error processing fresh element {i+1}: {e}")
                continue
        
        print(f"\n=== FRESH EXTRACTION COMPLETE: {len(comments)} comments ===")
        return comments

    def extract_comment_data_focused(self, element, index):
        """FOCUSED comment data extraction với enhanced UID resolution và stale element handling"""
        try:
            # Safe text extraction with stale element handling
            full_text = safe_get_element_text(element)
            if len(full_text) < 5:
                print(f"  ❌ Text too short: '{full_text}'")
                return None
            
            print(f"  Processing: '{full_text[:60]}...'")
            
            username = "Unknown"
            profile_href = ""
            uid = "Unknown"
            
            # FOCUSED: Enhanced username extraction with stale element protection
            print(f"    🎯 FOCUSED analysis of element structure...")
            
            # Method 1: Get ALL links and analyze each one with safe methods
            try:
                all_links = safe_find_elements(element, By.XPATH, ".//a")
                print(f"    Found {len(all_links)} total links in element")
                
                for link_index, link in enumerate(all_links):
                    try:
                        link_text = safe_get_element_text(link)
                        link_href = safe_get_element_attribute(link, "href")
                        
                        print(f"      Link {link_index+1}: Text='{link_text}' | Href={link_href[:60]}...")
                        
                        # Check if this is a Facebook profile link
                        if ('facebook.com' in link_href and 
                            ('profile.php' in link_href or '/user/' in link_href or 'user.php' in link_href or 
                             (not any(x in link_href for x in ['groups', 'pages', 'events', 'photo', 'video'])))):
                            
                            # Enhanced name validation với anonymous filter
                            if (link_text and 
                                len(link_text) >= 2 and 
                                len(link_text) <= 100 and
                                not link_text.isdigit() and
                                not link_text.startswith('http') and
                                not is_anonymous_user(link_text) and  # 🚫 BỎ QUA NGƯỜI DÙNG ẨN DANH
                                not any(ui in link_text.lower() for ui in [
                                    'like', 'reply', 'share', 'comment', 'thích', 'trả lời', 
                                    'chia sẻ', 'bình luận', 'ago', 'trước', 'min', 'hour', 
                                    'day', 'phút', 'giờ', 'ngày', 
                                    'view', 'xem', 'show', 'hiển thị', 'see more', 'view more'
                                ])):
                                
                                username = link_text
                                profile_href = link_href
                                
                                # Extract UID from URL trước
                                uid = extract_uid_from_profile_url(link_href)
                                
                                # Nếu UID vẫn chưa có hoặc là username, thử resolve
                                if uid == "Unknown" or uid.startswith("username:"):
                                    if uid.startswith("username:"):
                                        username_to_resolve = uid.split(":", 1)[1]
                                    else:
                                        username_to_resolve = username
                                    
                                    print(f"      🔄 Attempting to resolve UID for: {username_to_resolve}")
                                    resolved_uid = get_uid_from_username_enhanced(username_to_resolve, self.cookies_dict, self.driver, self._uid_cache)
                                    if resolved_uid != "Unknown":
                                        uid = resolved_uid
                                        print(f"      ✅ Successfully resolved UID: {uid}")
                                    else:
                                        print(f"      ⚠️ Could not resolve UID for: {username_to_resolve}")
                                
                                print(f"      ✅ FOCUSED: Found valid profile: {username} -> UID: {uid}")
                                break
                                
                    except Exception as e:
                        print(f"      Error processing link {link_index+1}: {e}")
                        continue
                
            except Exception as e:
                print(f"    Error in focused method: {e}")
            
            # Fallback: If no username from links, try using the first line of the first child element's text
            if username == "Unknown":
                try:
                    children = safe_find_elements(element, By.XPATH, "./*")
                    if children:
                        first_child_text = safe_get_element_text(children[0])
                        if first_child_text:
                            first_line = first_child_text.splitlines()[0].strip()
                            # Basic validation for a plausible name line + anonymous check
                            if (first_line and 
                                2 <= len(first_line) <= 120 and 
                                not first_line.startswith("http") and
                                not is_anonymous_user(first_line)):  # 🚫 BỎ QUA NGƯỜI DÙNG ẨN DANH
                                
                                username = first_line
                                print(f"      ✅ Fallback name from first child: {username}")
                                
                                # Thử resolve UID từ username fallback
                                print(f"      🔄 Attempting to resolve UID for fallback username: {username}")
                                resolved_uid = get_uid_from_username(username, self.cookies_dict, self.driver)
                                if resolved_uid != "Unknown":
                                    uid = resolved_uid
                                    print(f"      ✅ Successfully resolved UID from fallback: {uid}")
                            else:
                                if first_line and is_anonymous_user(first_line):
                                    print(f"      🚫 Skipped anonymous fallback username: {first_line}")
                                
                except Exception as e:
                    print(f"      ⚠️ Fallback name extraction error: {e}")

            # Final validation
            if username == "Unknown":
                print("  ❌ FOCUSED extraction failed for this element")
                return None
                
            print(f"  ✅ FOCUSED: Successfully extracted username: {username} | UID: {uid}")
            
            return {
                "UID": uid,
                "Name": username,
                "ProfileLink": profile_href,
                "CommentLink": "",
                "ElementIndex": index,
                "TextPreview": full_text[:100] + "..." if len(full_text) > 100 else full_text,
                "ContainerHeight": "Focused on larger height container"
            }
            
        except Exception as e:
            print(f"Error in focused extraction: {e}")
            return None

    def extract_comment_data_fast(self, element, index):
        """FAST comment data extraction WITHOUT UID resolution (for immediate processing)"""
        try:
            # Safe text extraction
            full_text = safe_get_element_text(element)
            if len(full_text) < 5:
                return None
            
            username = "Unknown"
            profile_href = ""
            immediate_uid = "Unknown"  # Initialize immediate_uid variable
            
            # FAST: Enhanced username extraction WITHOUT UID resolution
            try:
                all_links = safe_find_elements(element, By.XPATH, ".//a")
                
                for link in all_links:
                    try:
                        link_text = safe_get_element_text(link)
                        link_href = safe_get_element_attribute(link, "href")
                        
                        # DEBUG: Log all links để hiểu structure
                        if link_href and 'facebook.com' in link_href:
                            print(f"    🔗 DEBUG Link: '{link_text}' -> {link_href[:80]}...")
                        
                        # ENHANCED: Check if this is a Facebook profile link với nhiều pattern hơn
                        if (link_href and 'facebook.com' in link_href and 
                            ('profile.php' in link_href or '/user/' in link_href or 'user.php' in link_href or 
                             '/people/' in link_href or  # Thêm people pattern
                             (not any(x in link_href for x in ['groups', 'pages', 'events', 'photo', 'video', 'watch', 'reel'])))):
                            
                            # Enhanced name validation với anonymous filter
                            if (link_text and 
                                len(link_text) >= 2 and 
                                len(link_text) <= 100 and
                                not link_text.isdigit() and
                                not link_text.startswith('http') and
                                not is_anonymous_user(link_text) and  # 🚫 BỎ QUA NGƯỜI DÙNG ẨN DANH
                                not any(ui in link_text.lower() for ui in [
                                    'like', 'reply', 'share', 'comment', 'thích', 'trả lời', 
                                    'chia sẻ', 'bình luận', 'ago', 'trước', 'min', 'hour', 
                                    'day', 'phút', 'giờ', 'ngày', 
                                    'view', 'xem', 'show', 'hiển thị', 'see more', 'view more'
                                ])):
                                
                                username = link_text
                                profile_href = link_href
                                
                                # IMMEDIATE UID extraction từ profile link
                                immediate_uid = extract_uid_from_profile_url(link_href)
                                if immediate_uid != "Unknown":
                                    print(f"    ⚡ FAST: Immediate UID from URL: {immediate_uid}")
                                
                                # FALLBACK: Extract UID từ data attributes của link
                                if immediate_uid == "Unknown":
                                    data_attrs = ['data-hovercard', 'data-profileid', 'data-uid', 'data-id', 'data-userid']
                                    for attr in data_attrs:
                                        attr_value = safe_get_element_attribute(link, attr)
                                        if attr_value:
                                            uid_match = re.search(r'(\d{8,})', attr_value)
                                            if uid_match:
                                                immediate_uid = uid_match.group(1)
                                                print(f"    🎯 FAST: UID from {attr}: {immediate_uid}")
                                                break
                                
                                break
                                
                    except Exception as e:
                        continue
                
            except Exception as e:
                pass
            
            # Fallback: First child text (without UID resolution)
            if username == "Unknown":
                try:
                    children = safe_find_elements(element, By.XPATH, "./*")
                    if children:
                        first_child_text = safe_get_element_text(children[0])
                        if first_child_text:
                            first_line = first_child_text.splitlines()[0].strip()
                            if (first_line and 
                                2 <= len(first_line) <= 120 and 
                                not first_line.startswith("http") and
                                not is_anonymous_user(first_line)):
                                
                                username = first_line
                                
                except Exception as e:
                    pass

            # Final validation
            if username == "Unknown":
                return None
                
            # SUPER ENHANCED UID extraction với multiple methods
            uid = "Unknown"
            
            # Method 1: Sử dụng immediate_uid từ data attributes
            if immediate_uid != "Unknown":
                uid = immediate_uid
                print(f"    🎯 Using immediate UID from attributes: {uid}")
            
            # Method 2: Extract từ profile URL
            elif profile_href:
                uid = extract_uid_from_profile_url(profile_href)
                print(f"    🎯 UID from profile URL: {uid}")
            
            # Method 3: FALLBACK - Extract từ element attributes
            if uid == "Unknown":
                element_attrs = ['data-profileid', 'data-uid', 'data-id', 'data-userid', 'data-hovercard', 'id']
                for attr in element_attrs:
                    try:
                        attr_value = safe_get_element_attribute(element, attr)
                        if attr_value:
                            uid_match = re.search(r'(\d{8,})', attr_value)
                            if uid_match:
                                uid = uid_match.group(1)
                                print(f"    🔍 FALLBACK: UID from element {attr}: {uid}")
                                break
                    except:
                        continue
            
            # Method 4: Mark username for resolution nếu vẫn chưa có UID
            if uid == "Unknown" and profile_href:
                username_match = re.search(r'facebook\.com/([^/?]+)', profile_href)
                if username_match:
                    potential_username = username_match.group(1)
                    if not potential_username.isdigit() and len(potential_username) > 2:
                        uid = f"username:{potential_username}"
                        print(f"    🔄 Marked for resolution: {uid}")
            
            return {
                "UID": uid,  # Extract ngay thay vì để "Unknown"
                "Name": username,
                "ProfileLink": profile_href,
                "CommentLink": "",
                "ElementIndex": index,
                "TextPreview": full_text[:100] + "..." if len(full_text) > 100 else full_text,
                "ContainerHeight": "Fast extraction with immediate UID"
            }
            
        except Exception as e:
            return None

    def batch_resolve_uids(self, comments, max_network_resolves=10):
        """
        OPTIMIZED: Batch resolve UIDs với giới hạn network calls
        Args:
            comments (list): List of comments
            max_network_resolves (int): Max số lượng network calls
        Returns:
            int: Số UIDs resolved
        """
        print(f"🚀 BATCH UID resolution for {len(comments)} comments...")
        uid_resolved_count = 0
        network_resolves_used = 0
        
        # Phase 1: Fast URL-based resolution (no network)
        for comment in comments:
            if comment.get('UID') == "Unknown" and comment.get('ProfileLink'):
                fast_uid = extract_uid_from_profile_url(comment['ProfileLink'])
                if fast_uid != "Unknown" and not fast_uid.startswith("username:"):
                    comment['UID'] = fast_uid
                    uid_resolved_count += 1
        
        print(f"⚡ Phase 1: {uid_resolved_count} UIDs từ URLs")
        
        # Phase 2: Limited network resolution cho important cases
        if network_resolves_used < max_network_resolves:
            for comment in comments:
                if network_resolves_used >= max_network_resolves:
                    break
                    
                if comment.get('UID') == "Unknown" and comment.get('Name') != "Unknown":
                    # Chỉ resolve network cho users có profile link
                    if comment.get('ProfileLink'):
                        resolved_uid = get_uid_from_username(comment['Name'], self.cookies_dict, self.driver)
                        if resolved_uid != "Unknown":
                            comment['UID'] = resolved_uid
                            uid_resolved_count += 1
                            network_resolves_used += 1
                            print(f"  🌐 Network UID #{network_resolves_used}: {comment['Name']} -> {resolved_uid}")
        
        print(f"🎯 BATCH completed: {uid_resolved_count} total UIDs | {network_resolves_used} network calls")
        return uid_resolved_count

    def batch_resolve_uids_parallel(self, comments, max_network_resolves=10):
        """
        SUPER OPTIMIZED: Parallel UID resolution với caching và batching
        """
        import concurrent.futures
        from threading import Lock
        
        print(f"🚀 PARALLEL UID resolution for {len(comments)} comments (max network: {max_network_resolves})")
        
        uid_resolved_count = 0
        network_resolves_used = 0
        resolve_lock = Lock()
        
        # Phase 1: Fast URL-based resolution (no network) - PARALLEL
        url_resolved = 0
        for comment in comments:
            if comment.get('UID') == "Unknown" and comment.get('ProfileLink'):
                fast_uid = extract_uid_from_profile_url(comment['ProfileLink'])
                if fast_uid != "Unknown" and not fast_uid.startswith("username:"):
                    comment['UID'] = fast_uid
                    url_resolved += 1
        
        print(f"⚡ Phase 1: {url_resolved} UIDs resolved from URLs (instant)")
        uid_resolved_count += url_resolved
        
        # Phase 2: Parallel network resolution cho important cases
        if network_resolves_used < max_network_resolves:
            unresolved_comments = [c for c in comments if c.get('UID') == "Unknown" or c.get('UID', '').startswith("username:")][:max_network_resolves]
            
            def resolve_single_uid(comment_data):
                nonlocal network_resolves_used
                with resolve_lock:
                    if network_resolves_used >= max_network_resolves:
                        return None
                    network_resolves_used += 1
                
                try:
                    if comment_data.get('UID', '').startswith("username:"):
                        username_to_resolve = comment_data['UID'].split(":", 1)[1]
                    else:
                        username_to_resolve = comment_data.get('Name', '')
                    
                    if username_to_resolve and username_to_resolve != "Unknown":
                        # TRY CACHE FIRST
                        if username_to_resolve in self._uid_cache:
                            cached_uid = self._uid_cache[username_to_resolve]
                            comment_data['UID'] = cached_uid
                            print(f"  ⚡ CACHE: {username_to_resolve} -> {cached_uid}")
                            return 1 if cached_uid != "Unknown" else 0
                        
                        resolved_uid = get_uid_from_username_enhanced(username_to_resolve, self.cookies_dict, self.driver, self._uid_cache)
                        if resolved_uid != "Unknown":
                            comment_data['UID'] = resolved_uid
                            return 1
                except Exception as e:
                    print(f"⚠️ Parallel resolve error for {username_to_resolve}: {e}")
                return 0
            
            # Execute parallel resolution với ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_to_comment = {executor.submit(resolve_single_uid, comment): comment for comment in unresolved_comments}
                
                for future in concurrent.futures.as_completed(future_to_comment, timeout=30):
                    try:
                        result = future.result()
                        if result:
                            uid_resolved_count += result
                    except Exception as e:
                        print(f"⚠️ Parallel execution error: {e}")
        
        print(f"🎯 PARALLEL completed: {uid_resolved_count} total UIDs | {network_resolves_used} network calls")
        return uid_resolved_count

    def extract_comments_bulk_optimized(self, max_comments=1000):
        """
        BULK OPTIMIZED: Extraction cho 1k+ comments với performance tối đa
        """
        print(f"🚀 BULK OPTIMIZED extraction for up to {max_comments} comments")
        
        all_comments_data = []
        seen_content = set()
        
        # ENHANCED scrolling để load nhiều comments hơn
        print("⚡ ENHANCED scrolling to load ALL comments...")
        
        # Phase 1: Aggressive scrolling để trigger comment loading
        previous_height = 0
        scroll_attempts = 0
        max_scroll_attempts = 20  # Tăng từ 10 lên 20
        
        while scroll_attempts < max_scroll_attempts:
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)  # Tăng thời gian chờ để comments load
            
            # Check if new content loaded
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height > previous_height:
                previous_height = new_height
                print(f"  📈 Scroll {scroll_attempts + 1}: New content loaded (height: {new_height})")
            else:
                print(f"  ⏸️ Scroll {scroll_attempts + 1}: No new content")
            
            scroll_attempts += 1
            
            # Also scroll up a bit to trigger lazy loading
            if scroll_attempts % 3 == 0:
                self.driver.execute_script("window.scrollBy(0, -500);")
                time.sleep(0.2)
                self.driver.execute_script("window.scrollBy(0, 500);")
        
        print(f"✅ Completed {scroll_attempts} scroll attempts")
        
        # ENHANCED clicking để load ALL possible comments
        print("🔄 ENHANCED clicking to load ALL comments...")
        
        # Phase 1: Try all possible "View more" buttons
        total_clicks = 0
        max_click_attempts = 15  # Tăng từ 8 lên 15
        consecutive_fails = 0
        max_consecutive_fails = 3
        
        for click_attempt in range(max_click_attempts):
            try:
                # Enhanced selectors - bao gồm nhiều ngôn ngữ và formats
                view_more_selectors = [
                    # English
                    "//button[contains(text(), 'View more comments')]",
                    "//a[contains(text(), 'View more comments')]",
                    "//span[contains(text(), 'View more comments')]",
                    "//div[contains(text(), 'View more comments')]",
                    "//*[contains(text(), 'View more')]",
                    "//*[contains(text(), 'Show more')]",
                    "//*[contains(text(), 'Load more')]",
                    "//*[contains(text(), 'See more')]",
                    
                    # Vietnamese
                    "//*[contains(text(), 'Xem thêm')]",
                    "//*[contains(text(), 'Hiển thị thêm')]",
                    "//*[contains(text(), 'Tải thêm')]",
                    
                    # By class/attributes
                    "//button[contains(@class, 'view-more')]",
                    "//button[contains(@class, 'show-more')]",
                    "//*[@role='button' and contains(text(), 'more')]"
                ]
                
                clicked = False
                elements_found = 0
                
                for selector in view_more_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        elements_found += len(elements)
                        
                        for element in elements:
                            try:
                                # Check if element is visible and clickable
                                if element.is_displayed() and element.is_enabled():
                                    # Scroll to element first
                                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                                    time.sleep(0.5)
                                    
                                    # Try click
                                    self.driver.execute_script("arguments[0].click();", element)
                                    clicked = True
                                    total_clicks += 1
                                    print(f"  ✅ Click {click_attempt + 1}: SUCCESS (selector: {selector[:50]}...)")
                                    time.sleep(1.5)  # Tăng thời gian chờ để comments load
                                    break
                            except Exception as click_error:
                                continue
                        
                        if clicked:
                            break
                            
                    except Exception as selector_error:
                        continue
                
                if clicked:
                    consecutive_fails = 0
                    
                    # After each successful click, do a quick scroll to load more
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
                    
                else:
                    consecutive_fails += 1
                    print(f"  ❌ Click {click_attempt + 1}: No clickable buttons found ({elements_found} elements found)")
                    
                    if consecutive_fails >= max_consecutive_fails:
                        print(f"  ⏹️ Stopping after {consecutive_fails} consecutive failures")
                        break
                    
            except Exception as e:
                print(f"  ⚠️ Click {click_attempt + 1} failed: {e}")
                consecutive_fails += 1
                if consecutive_fails >= max_consecutive_fails:
                    break
        
        print(f"✅ Completed clicking phase: {total_clicks} successful clicks")
        
        # BULK extraction tất cả comments cùng lúc
        print("📦 BULK extracting all visible comments...")
        all_elements = self.extract_all_fresh_comments()
        
        # Process theo chunks lớn
        chunk_size = 50  # Xử lý 50 comments mỗi chunk
        total_chunks = (len(all_elements) + chunk_size - 1) // chunk_size
        
        for chunk_idx in range(total_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min(start_idx + chunk_size, len(all_elements))
            chunk_elements = all_elements[start_idx:end_idx]
            
            print(f"📦 Processing chunk {chunk_idx + 1}/{total_chunks}: {len(chunk_elements)} comments")
            
            # Batch process chunk
            chunk_comments = []
            for element in chunk_elements:
                try:
                    comment_data = self.extract_comment_data_fast(element, len(all_comments_data))
                    if comment_data and comment_data['Name'] != "Unknown":
                        if not is_anonymous_user(comment_data['Name']):
                            content_signature = f"{comment_data['Name']}_{comment_data['ProfileLink']}"
                            if content_signature not in seen_content:
                                seen_content.add(content_signature)
                                comment_data['Type'] = 'Comment'
                                comment_data['Layout'] = self.current_layout
                                comment_data['Source'] = f'Bulk Chunk {chunk_idx + 1}'
                                chunk_comments.append(comment_data)
                except:
                    continue
            
            all_comments_data.extend(chunk_comments)
            print(f"  ✅ Chunk {chunk_idx + 1}: +{len(chunk_comments)} new comments (total: {len(all_comments_data)})")
            
            # Early exit nếu đã đủ comments
            if len(all_comments_data) >= max_comments:
                print(f"🎯 BULK target reached: {len(all_comments_data)} comments")
                break
        
        print(f"✅ BULK extraction completed: {len(all_comments_data)} comments")
        
        # FINAL CHECK: Try to get more comments if we didn't reach target
        if len(all_comments_data) < max_comments * 0.8:  # If we got less than 80% of target
            print(f"⚠️ Got {len(all_comments_data)} comments, trying additional extraction...")
            
            # Try one more aggressive scroll and click cycle
            print("🔄 Additional extraction attempt...")
            
            # More aggressive scrolling
            for i in range(10):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.3)
                self.driver.execute_script("window.scrollBy(0, -200);")
                time.sleep(0.2)
                self.driver.execute_script("window.scrollBy(0, 200);")
                time.sleep(0.3)
            
            # Try to find and click any remaining "View more" buttons
            additional_buttons = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'View more') or contains(text(), 'Show more') or contains(text(), 'Xem thêm')]")
            for button in additional_buttons[:5]:  # Try up to 5 more buttons
                try:
                    if button.is_displayed() and button.is_enabled():
                        self.driver.execute_script("arguments[0].click();", button)
                        time.sleep(2)
                        print("  ✅ Clicked additional 'View more' button")
                except:
                    continue
            
            # Extract again
            additional_elements = self.extract_all_fresh_comments()
            print(f"📦 Additional extraction found {len(additional_elements)} elements")
            
            # Process additional elements
            additional_comments = []
            for element in additional_elements:
                try:
                    comment_data = self.extract_comment_data_fast(element, len(all_comments_data))
                    if comment_data and comment_data['Name'] != "Unknown":
                        if not is_anonymous_user(comment_data['Name']):
                            content_signature = f"{comment_data['Name']}_{comment_data['ProfileLink']}"
                            if content_signature not in seen_content:
                                seen_content.add(content_signature)
                                comment_data['Type'] = 'Comment'
                                comment_data['Layout'] = self.current_layout
                                comment_data['Source'] = 'Additional Extraction'
                                additional_comments.append(comment_data)
                except:
                    continue
            
            all_comments_data.extend(additional_comments)
            print(f"  ✅ Additional extraction added {len(additional_comments)} new comments")
            print(f"📊 Final total: {len(all_comments_data)} comments")
        
        return all_comments_data

    def scrape_all_comments(self, limit=0, resolve_uid=True, progress_callback=None):
        """Main scraping orchestrator with FOCUSED approach"""
        print(f"=== STARTING FOCUSED GROUPS SCRAPING ===")
        
        # Reset counters
        self._anonymous_filtered_count = 0
        
        if self._stop_flag:
            return []
        
        # Step 1: Extract comments - sử dụng bulk method cho 1k+ comments
        if limit >= 1000:
            print("🚀 Using BULK OPTIMIZED method for 1k+ comments")
            comments = self.extract_comments_bulk_optimized(max_comments=limit or 1000)
        else:
            comments = self.extract_groups_comments()
        
        # Step 2: Filter out anonymous users BEFORE UID resolution
        if comments:
            print(f"\n🚫 Filtering anonymous users from {len(comments)} comments...")
            filtered_comments = []
            anonymous_count = 0
            
            for comment in comments:
                if comment.get('Name') == "Unknown":
                    continue
                    
                if is_anonymous_user(comment['Name']):
                    anonymous_count += 1
                    print(f"  🚫 Filtered anonymous: {comment['Name']}")
                    continue
                    
                filtered_comments.append(comment)
            
            # Store count for statistics
            self._anonymous_filtered_count = anonymous_count
            
            print(f"  📊 Filtered out {anonymous_count} anonymous users")
            print(f"  ✅ Remaining: {len(filtered_comments)} real users")
            comments = filtered_comments
        
        # Step 3: SUPER OPTIMIZED UID resolution với parallel processing
        if resolve_uid and comments:
            uid_resolved_count = self.batch_resolve_uids_parallel(comments, max_network_resolves=10)  # Tăng limit và thêm parallel
        
        # Step 4: Apply limit
        if limit > 0 and len(comments) > limit:
            comments = comments[:limit]
            print(f"📊 Limited to {limit} comments")
        
        # Step 5: Progress reporting
        if progress_callback:
            progress_callback(len(comments))
        
        # Statistics
        uid_count = len([c for c in comments if c.get('UID', 'Unknown') != 'Unknown'])
        anonymous_filtered = self._anonymous_filtered_count
        uid_rate = (uid_count / len(comments)) * 100 if comments else 0
        print(f"✅ OPTIMIZED scraping completed: {len(comments)} real users | {uid_count} UIDs ({uid_rate:.1f}%) | {anonymous_filtered} anonymous filtered")
        return comments

    def debug_uid_extraction(self, comments_sample=5):
        """
        🐛 DEBUG: Kiểm tra tại sao UID extraction không hoạt động
        """
        print(f"🐛 DEBUG UID EXTRACTION - Analyzing {comments_sample} comments...")
        
        comments = self.extract_all_fresh_comments()[:comments_sample]
        
        for i, element in enumerate(comments):
            print(f"\n--- DEBUG Comment {i+1} ---")
            try:
                # Extract text
                full_text = safe_get_element_text(element)
                print(f"📝 Text: {full_text[:100]}...")
                
                # Find all links
                all_links = safe_find_elements(element, By.XPATH, ".//a")
                print(f"🔗 Found {len(all_links)} links:")
                
                for j, link in enumerate(all_links):
                    try:
                        link_text = safe_get_element_text(link)
                        link_href = safe_get_element_attribute(link, "href")
                        print(f"  Link {j+1}: '{link_text}' -> {link_href}")
                        
                        if link_href and 'facebook.com' in link_href:
                            uid_result = extract_uid_from_profile_url(link_href)
                            print(f"    UID extraction result: {uid_result}")
                            
                    except Exception as e:
                        print(f"  Error processing link {j+1}: {e}")
                        
            except Exception as e:
                print(f"Error processing comment {i+1}: {e}")
        
        print(f"🐛 DEBUG UID EXTRACTION COMPLETE")

    def test_username_to_uid(self, test_usernames=None):
        """
        🧪 TEST: Test username to UID conversion
        """
        if not test_usernames:
            test_usernames = ["john.doe", "jane.smith.123", "testuser2024"]
        
        print(f"🧪 Testing username to UID conversion for {len(test_usernames)} usernames...")
        
        for i, username in enumerate(test_usernames):
            print(f"\n--- Test {i+1}: {username} ---")
            
            try:
                # Test enhanced method
                uid = get_uid_from_username_enhanced(username, self.cookies_dict, self.driver, self._uid_cache)
                print(f"Result: {uid}")
                
                if uid != "Unknown":
                    print(f"✅ SUCCESS: {username} -> {uid}")
                else:
                    print(f"❌ FAILED: Could not resolve {username}")
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")
        
        print(f"🧪 Username to UID test complete!")

    def test_uid_extraction_quick(self):
        """
        🧪 QUICK TEST: Test UID extraction trên 5 comments đầu tiên
        """
        print("🧪 QUICK UID EXTRACTION TEST...")
        
        try:
            # Get first 5 comment elements
            elements = self.extract_all_fresh_comments()[:5]
            print(f"📊 Testing on {len(elements)} comment elements")
            
            for i, element in enumerate(elements):
                print(f"\n--- TEST Comment {i+1} ---")
                comment_data = self.extract_comment_data_fast(element, i)
                if comment_data:
                    print(f"✅ Name: {comment_data['Name']}")
                    print(f"✅ UID: {comment_data['UID']}")
                    print(f"✅ ProfileLink: {comment_data['ProfileLink'][:80]}...")
                else:
                    print("❌ No data extracted")
            
            print("🧪 QUICK TEST COMPLETE")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")

    def scrape_1k_comments_optimized(self, progress_callback=None):
        """
        🚀 SIÊU TỐI ƯU cho 1k comments - Wrapper method
        """
        print("🚀🚀🚀 SIÊU TỐI ƯU CHO 1K COMMENTS 🚀🚀🚀")
        
        start_time = time.time()
        
        # Clear cache để bắt đầu fresh
        self._uid_cache.clear()
        self._profile_cache.clear()
        self._element_cache.clear()
        
        # Sử dụng bulk method với limit 1000
        comments = self.scrape_all_comments(limit=1000, resolve_uid=True, progress_callback=progress_callback)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        print(f"⏱️ PERFORMANCE REPORT:")
        print(f"   📊 Processed: {len(comments)} comments")
        print(f"   ⏰ Time taken: {elapsed:.2f} seconds")
        print(f"   ⚡ Speed: {len(comments)/elapsed:.1f} comments/second")
        print(f"   💾 UID Cache hits: {len(self._uid_cache)} entries")
        
        return comments

    def close(self):
        try: 
            self.driver.quit()
        except: 
            pass

# ----------------------------
# FOCUSED GUI
# ----------------------------

class FBGroupsAppGUI:
    def __init__(self, root):
        self.root = root
        root.title("🎯 FB Groups Comment Scraper - FOCUSED + UID")
        root.geometry("1100x950")
        root.configure(bg="#121212")

        # Main frame
        main_frame = tk.Frame(root, bg="#121212")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # Header
        header_frame = tk.Frame(main_frame, bg="#121212")
        header_frame.pack(fill="x", pady=(0,20))
        
        title_label = tk.Label(header_frame, text="🎯 FB Groups Scraper - FOCUSED + UID + Anonymous Filter", 
                              font=("Arial", 20, "bold"), bg="#121212", fg="#a5d6a7")
        title_label.pack()
        
        subtitle_label = tk.Label(header_frame, text="🎯 Enhanced: Extracts usernames + UIDs + Skips anonymous users", 
                                 font=("Arial", 11), bg="#121212", fg="#b0b0b0")
        subtitle_label.pack(pady=(5,0))

        # Input section
        input_frame = tk.LabelFrame(main_frame, text="📝 Thông tin bài viết Groups", font=("Arial", 12, "bold"), 
                                   bg="#121212", fg="#a5d6a7", relief="groove", bd=2)
        input_frame.pack(fill="x", pady=(0,15))

        tk.Label(input_frame, text="🔗 Link bài viết trong Groups:", bg="#121212", font=("Arial", 10)).pack(anchor="w", padx=15, pady=(15,5))
        self.entry_url = tk.Entry(input_frame, width=100, font=("Arial", 9))
        self.entry_url.pack(fill="x", padx=15, pady=(0,10))

        tk.Label(input_frame, text="🍪 Cookie Facebook (để truy cập Groups):", bg="#121212", font=("Arial", 10)).pack(anchor="w", padx=15, pady=(5,5))
        self.txt_cookie = tk.Text(input_frame, height=4, font=("Arial", 8))
        self.txt_cookie.pack(fill="x", padx=15, pady=(0,15))

        # Options section
        options_frame = tk.LabelFrame(main_frame, text="🎯 Cấu hình FOCUSED + UID + Anonymous Filter", font=("Arial", 12, "bold"), 
                                     bg="#121212", fg="#a5d6a7", relief="groove", bd=2)
        options_frame.pack(fill="x", pady=(0,15))
        
        opt_grid = tk.Frame(options_frame, bg="#121212")
        opt_grid.pack(fill="x", padx=15, pady=15)
        
        # Options grid
        tk.Label(opt_grid, text="📊 Số lượng comment:", bg="#121212").grid(row=0, column=0, sticky="w")
        self.entry_limit = tk.Entry(opt_grid, width=10)
        self.entry_limit.insert(0, "0")
        self.entry_limit.grid(row=0, column=1, sticky="w", padx=(10,20))
        tk.Label(opt_grid, text="(0 = tất cả)", bg="#121212", fg="#6c757d").grid(row=0, column=2, sticky="w")

        self.headless_var = tk.BooleanVar(value=False)  # Default to visible for debugging
        tk.Checkbutton(opt_grid, text="👻 Chạy ẩn", variable=self.headless_var,
                      bg="#121212", font=("Arial", 9)).grid(row=1, column=0, sticky="w", pady=(10,0))

        self.resolve_uid_var = tk.BooleanVar(value=False)  # Default False cho speed
        tk.Checkbutton(opt_grid, text="🆔 Lấy UID từ username (chậm hơn)", variable=self.resolve_uid_var, 
                      bg="#121212", font=("Arial", 9)).grid(row=1, column=1, sticky="w", pady=(10,0))

        # Speed mode option
        self.speed_mode_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_grid, text="⚡ Speed mode (giới hạn 50 comments)", variable=self.speed_mode_var,
                      bg="#121212", font=("Arial", 9)).grid(row=2, column=0, sticky="w", pady=(5,0))

        # Thêm note về anonymous filter
        tk.Label(opt_grid, text="🚫 Tự động bỏ qua người dùng ẩn danh", bg="#121212", fg="#ffc107", 
                font=("Arial", 9, "italic")).grid(row=3, column=0, columnspan=3, sticky="w", pady=(5,0))

        # File section
        file_frame = tk.LabelFrame(main_frame, text="💾 Xuất kết quả", font=("Arial", 12, "bold"), 
                                  bg="#121212", fg="#a5d6a7", relief="groove", bd=2)
        file_frame.pack(fill="x", pady=(0,15))
        
        file_row = tk.Frame(file_frame, bg="#121212")
        file_row.pack(fill="x", padx=15, pady=15)
        
        self.entry_file = tk.Entry(file_row, width=70, font=("Arial", 9))
        current_date = datetime.now().strftime("%d_%m_%Y")
        self.entry_file.insert(0, f"facebook_groups_comments_UID_NoAnonymous_{current_date}.xlsx")
        self.entry_file.pack(side="left", fill="x", expand=True)
        
        self.btn_choose = tk.Button(file_row, text="📁 Chọn", command=self.choose_file, 
                 bg="#17a2b8", fg="black", font=("Arial", 9))
        self.btn_choose.pack(side="right", padx=(10,0))

        # Status section
        status_frame = tk.LabelFrame(main_frame, text="📊 Trạng thái thực thi - ENHANCED UID + ANONYMOUS FILTER", font=("Arial", 12, "bold"), 
                                    bg="#121212", fg="#a5d6a7", relief="groove", bd=2)
        status_frame.pack(fill="x", pady=(0,15))
        
        self.lbl_status = tk.Label(status_frame, text="✅ Enhanced UID + Anonymous Filter scraper sẵn sàng - Tự động bỏ qua người dùng ẩn danh", fg="#28a745", 
                                  wraplength=900, justify="left", font=("Arial", 11), bg="#121212")
        self.lbl_status.pack(anchor="w", padx=15, pady=(15,5))

        self.lbl_progress_detail = tk.Label(status_frame, text="💡 NEW: Username → UID conversion | Anonymous filtering | Stale element protection | Enhanced debugging",
                                          fg="#b0b0b0", wraplength=900, justify="left", font=("Arial", 9), bg="#121212")
        self.lbl_progress_detail.pack(anchor="w", padx=15, pady=(0,10))

        # Progress bar
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress_bar.pack(fill="x", padx=15, pady=(0,15))

        # Control buttons
        button_frame = tk.Frame(main_frame, bg="#121212")
        button_frame.pack(fill="x", pady=20)
        
        self.btn_start = tk.Button(button_frame, text="🚀 Bắt đầu UID + Filter Scraping", bg="#28a745", fg="black", 
                                  font=("Arial", 14, "bold"), command=self.start_scrape_thread, 
                                  pady=12, padx=40)
        self.btn_start.pack(side="left")

        self.btn_stop = tk.Button(button_frame, text="⏹️ Dừng", bg="#dc3545", fg="black", 
                                 font=("Arial", 14, "bold"), command=self.stop_scrape, 
                                 state=tk.DISABLED, pady=12, padx=40)
        self.btn_stop.pack(side="left", padx=(25,0))
        
        # Thêm TEST buttons cho debugging
        self.btn_test_uid = tk.Button(button_frame, text="🧪 Test UID", bg="#ffc107", fg="black", 
                                     font=("Arial", 12, "bold"), command=self.test_uid_extraction, 
                                     pady=8, padx=20)
        self.btn_test_uid.pack(side="left", padx=(25,0))
        
        self.btn_test_username = tk.Button(button_frame, text="👤 Test Username→UID", bg="#6f42c1", fg="white", 
                                          font=("Arial", 10, "bold"), command=self.test_username_to_uid, 
                                          pady=6, padx=15)
        self.btn_test_username.pack(side="left", padx=(10,0))

        self.progress_var = tk.IntVar(value=0)
        self.progress_label = tk.Label(button_frame, textvariable=self.progress_var, fg="#28a745", 
                                     font=("Arial", 18, "bold"), bg="#121212")
        self.progress_label.pack(side="right")

        self._scrape_thread = None
        self._stop_flag = False
        self.scraper = None

        # Apply dark theme across widgets
        self._apply_dark_theme()

        # Beautify primary (start) and danger (stop) buttons
        self._beautify_button(self.btn_start, base_bg="#2ecc71", hover_bg="#27ae60", active_bg="#1e874b")
        self._beautify_button(self.btn_stop, base_bg="#e74c3c", hover_bg="#c0392b", active_bg="#992d22")
        # Beautify choose file button with cyan palette
        self._beautify_button(self.btn_choose, base_bg="#17a2b8", hover_bg="#1491a1", active_bg="#0f6f7b")

    def _apply_dark_theme(self):
        """Apply a dark theme recursively to Tk widgets and ttk components."""
        dark_bg = "#121212"
        surface_bg = "#1e1e1e"
        light_fg = "#e0e0e0"
        subtle_fg = "#b0b0b0"

        # Root background
        try:
            self.root.configure(bg=dark_bg)
        except Exception:
            pass

        def apply(widget):
            # Background
            try:
                if 'background' in widget.configure():
                    widget.configure(bg=dark_bg)
            except Exception:
                pass

            # Foreground: only adjust if currently black/dark default
            try:
                # Skip changing foreground for clickable buttons so custom styles persist
                if isinstance(widget, tk.Button):
                    pass
                else:
                    cfg = widget.configure()
                    if 'foreground' in cfg:
                        current_fg = str(widget.cget('fg')).lower()
                        if current_fg in ('black', '#000000'):
                            widget.configure(fg=light_fg)
            except Exception:
                pass

            # Special cases
            try:
                if isinstance(widget, tk.Entry):
                    widget.configure(bg=surface_bg, fg=light_fg, insertbackground=light_fg)
                if isinstance(widget, tk.Text):
                    widget.configure(bg=surface_bg, fg=light_fg, insertbackground=light_fg)
                if isinstance(widget, tk.Listbox):
                    widget.configure(bg=surface_bg, fg=light_fg, selectbackground="#2a2a2a")
            except Exception:
                pass

            for child in widget.winfo_children():
                apply(child)

        apply(self.root)

        # ttk styling (progress bar)
        try:
            style = ttk.Style()
            # Use a theme that allows color customization
            try:
                style.theme_use('clam')
            except Exception:
                pass
            style.configure("TProgressbar",
                            troughcolor=surface_bg,
                            background="#00bcd4",
                            bordercolor=surface_bg,
                            lightcolor=surface_bg,
                            darkcolor=surface_bg)
        except Exception:
            pass

    def _beautify_button(self, button, base_bg="#2ecc71", hover_bg="#27ae60", active_bg="#1e874b"):
        """Apply modern flat styling and hover/active effects to tk.Button."""
        try:
            button.configure(
                bg=base_bg,
                fg="#000000",
                activebackground=active_bg,
                activeforeground="#000000",
                bd=0,
                highlightthickness=0,
                relief="flat",
                cursor="hand2",
                disabledforeground="#777777"
            )

            def on_enter(_):
                try:
                    button.configure(bg=hover_bg)
                except Exception:
                    pass

            def on_leave(_):
                try:
                    button.configure(bg=base_bg)
                except Exception:
                    pass

            def on_press(_):
                try:
                    button.configure(bg=active_bg)
                except Exception:
                    pass

            def on_release(_):
                try:
                    button.configure(bg=hover_bg)
                except Exception:
                    pass

            button.bind("<Enter>", on_enter)
            button.bind("<Leave>", on_leave)
            button.bind("<ButtonPress-1>", on_press)
            button.bind("<ButtonRelease-1>", on_release)
        except Exception:
            pass

    def choose_file(self):
        f = filedialog.asksaveasfilename(
            defaultextension=".xlsx", 
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")],
            title="Chọn file để lưu Groups comments với UID"
        )
        if f:
            self.entry_file.delete(0, tk.END)
            self.entry_file.insert(0, f)

    def start_scrape_thread(self):
        url = self.entry_url.get().strip()
        cookie_str = self.txt_cookie.get("1.0", tk.END).strip()
        file_out = self.entry_file.get().strip() or "facebook_groups_comments_UID.xlsx"
        
        if not url:
            messagebox.showerror("❌ Lỗi", "Vui lòng nhập link bài viết Groups.")
            return
        
        if "groups/" not in url:
            result = messagebox.askyesno("⚠️ Xác nhận", 
                                       "Link này có vẻ không phải Groups. Bạn có muốn tiếp tục không?")
            if not result:
                return
        
        try: 
            limit = int(self.entry_limit.get().strip())
        except: 
            limit = 0

        self._stop_flag = False
        self.progress_var.set(0)
        self.progress_bar.start()
        self.lbl_status.config(text="🔄 Đang khởi động Enhanced UID Groups scraper...", fg="#fd7e14")
        self.lbl_progress_detail.config(text="⏳ Initializing UID extraction with Selenium + Requests methods...")
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)

        self._scrape_thread = threading.Thread(target=self._scrape_worker, 
                                             args=(url, cookie_str, file_out, limit, 
                                                   self.headless_var.get(), self.resolve_uid_var.get(),
                                                   self.speed_mode_var.get()))
        self._scrape_thread.daemon = True
        self._scrape_thread.start()

    def stop_scrape(self):
        self._stop_flag = True
        if self.scraper:
            self.scraper._stop_flag = True
        self.lbl_status.config(text="⏹️ Đang dừng UID scraper...", fg="#dc3545")
        self.btn_stop.config(state=tk.DISABLED)

    def test_uid_extraction(self):
        """🧪 Test UID extraction để debug"""
        try:
            if not self.scraper:
                post_url = self.entry_url.get().strip()
                if not post_url:
                    messagebox.showerror("Lỗi", "Vui lòng nhập URL post trước!")
                    return
                
                # Initialize scraper
                cookie_str = self.text_cookie.get("1.0", tk.END).strip()
                if not cookie_str:
                    messagebox.showerror("Lỗi", "Vui lòng nhập cookie trước!")
                    return
                
                self.scraper = FacebookGroupsScraper(cookie_str, self.headless_var.get())
                self.scraper.load_post(post_url)
            
            # Run test
            self.lbl_status.config(text="🧪 Testing UID extraction...", fg="#ffc107")
            self.scraper.test_uid_extraction_quick()
            self.lbl_status.config(text="✅ Test completed! Check console for details.", fg="#28a745")
            
        except Exception as e:
            self.lbl_status.config(text=f"❌ Test failed: {str(e)}", fg="#dc3545")
            messagebox.showerror("Test Error", f"Lỗi test UID: {str(e)}")

    def test_username_to_uid(self):
        """👤 Test username to UID conversion"""
        try:
            if not self.scraper:
                post_url = self.entry_url.get().strip()
                if not post_url:
                    messagebox.showerror("Lỗi", "Vui lòng nhập URL post trước!")
                    return
                
                # Initialize scraper
                cookie_str = self.text_cookie.get("1.0", tk.END).strip()
                if not cookie_str:
                    messagebox.showerror("Lỗi", "Vui lòng nhập cookie trước!")
                    return
                
                self.scraper = FacebookGroupsScraper(cookie_str, self.headless_var.get())
                self.scraper.load_post(post_url)
            
            # Prompt for usernames to test
            usernames_input = tk.simpledialog.askstring(
                "Test Username→UID", 
                "Nhập usernames để test (cách nhau bằng dấu phẩy):\nVí dụ: john.doe, jane.smith.123, testuser",
                initialvalue="john.doe, jane.smith"
            )
            
            if usernames_input:
                usernames = [u.strip() for u in usernames_input.split(',') if u.strip()]
                self.lbl_status.config(text=f"👤 Testing {len(usernames)} usernames...", fg="#6f42c1")
                
                # Run test
                self.scraper.test_username_to_uid(usernames)
                self.lbl_status.config(text="✅ Username test completed! Check console.", fg="#28a745")
            else:
                self.lbl_status.config(text="❌ No usernames provided", fg="#dc3545")
                
        except Exception as e:
            self.lbl_status.config(text=f"❌ Username test failed: {str(e)}", fg="#dc3545")
            messagebox.showerror("Username Test Error", f"Lỗi test username: {str(e)}")

    def _progress_cb(self, count):
        self.progress_var.set(count)
        self.lbl_status.config(text=f"📈 UID processing... Đã lấy {count} comments", fg="#28a745")
        self.root.update_idletasks()

    def _scrape_worker(self, url, cookie_str, file_out, limit, headless, resolve_uid, speed_mode=True):
        try:
            # Initialize
            self.lbl_status.config(text="🌐 Khởi tạo Enhanced UID Groups scraper...", fg="#fd7e14")
            self.scraper = FacebookGroupsScraper(cookie_str, headless=headless)
            
            if self._stop_flag: return
            
            # Load post
            self.lbl_status.config(text="📄 Đang tải bài viết Groups với UID logic...", fg="#fd7e14")
            self.lbl_progress_detail.config(text="⏳ Loading post with enhanced UID resolution...")
            success = self.scraper.load_post(url)
            
            if not success:
                self.lbl_status.config(text="❌ Không thể tải bài viết Groups", fg="#dc3545")
                self.lbl_progress_detail.config(text="💡 Kiểm tra: 1) Cookie valid, 2) Quyền truy cập Groups, 3) Link chính xác")
                return
            
            # Show detected layout
            layout = getattr(self.scraper, 'current_layout', 'unknown')
            self.lbl_progress_detail.config(text=f"🎯 Layout detected: {layout} - Using Enhanced UID extraction...")
                
            if self._stop_flag: return
            
            # Scrape with Enhanced UID logic
            mode_text = "⚡ SPEED MODE" if speed_mode else "🔍 FULL MODE"
            self.lbl_status.config(text=f"{mode_text} Groups extraction ({layout})...", fg="#fd7e14")
            
            if speed_mode:
                self.lbl_progress_detail.config(text="⚡ Speed mode: Fast extraction, limited UID resolution...")
                # Override settings cho speed mode
                actual_limit = min(limit, 50) if limit > 0 else 50
                actual_resolve_uid = False  # Disable UID resolution trong speed mode
            else:
                self.lbl_progress_detail.config(text="⏳ Full mode: Complete extraction với UID resolution...")
                actual_limit = limit
                actual_resolve_uid = resolve_uid
            
            comments = self.scraper.scrape_all_comments(limit=actual_limit, resolve_uid=actual_resolve_uid, 
                                                       progress_callback=self._progress_cb)
            
            # SPEED MODE: Extract UIDs từ URLs có sẵn (không cần network)
            if speed_mode and comments:
                print(f"\n⚡ SPEED MODE: Fast UID extraction từ URLs...")
                url_uid_count = 0
                for comment in comments:
                    if comment.get('UID') == "Unknown" and comment.get('ProfileLink'):
                        fast_uid = extract_uid_from_profile_url(comment['ProfileLink'])
                        if fast_uid != "Unknown" and not fast_uid.startswith("username:"):
                            comment['UID'] = fast_uid
                            url_uid_count += 1
                
                print(f"⚡ Speed UID extraction: {url_uid_count} UIDs từ URLs")
            
            print(f"✅ Comments: {len(comments)} | Speed mode: {speed_mode}")

            if self._stop_flag: return
            
            # Save
            self.lbl_status.config(text="💾 Đang lưu Enhanced UID Groups data...", fg="#fd7e14")
            
            if comments:
                df = pd.DataFrame(comments)
                
                # Add metadata
                df.insert(0, 'STT', range(1, len(df) + 1))
                df['Source'] = 'Facebook Groups - Enhanced UID'
                df['ScrapedAt'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # File handling
                if not file_out.lower().endswith((".xlsx", ".csv")):
                    file_out += ".xlsx"
                
                if file_out.lower().endswith(".csv"):
                    df.to_csv(file_out, index=False, encoding="utf-8-sig")
                else:
                    df.to_excel(file_out, index=False, engine="openpyxl")
                
                # Statistics
                unique_users = len(set(c['Name'] for c in comments if c['Name'] != 'Unknown'))
                profile_links = len([c for c in comments if c['ProfileLink']])
                uid_count = len([c for c in comments if c.get('UID', 'Unknown') != 'Unknown'])
                uid_success_rate = (uid_count / len(comments)) * 100 if comments else 0
                anonymous_filtered = getattr(self.scraper, '_anonymous_filtered_count', 0)
                
                mode_emoji = "⚡" if speed_mode else "🔍"
                mode_text = "SPEED MODE" if speed_mode else "FULL MODE"
                
                self.lbl_status.config(text=f"🎉 {mode_emoji} {mode_text} SCRAPING HOÀN THÀNH!", fg="#28a745")
                self.lbl_progress_detail.config(text=f"📊 {mode_text}: {len(comments)} users | {uid_count} UIDs ({uid_success_rate:.1f}%) | 🚫 {anonymous_filtered} anonymous | {layout}")
                
                print(f"🎯 {mode_emoji} {mode_text} SCRAPING COMPLETE!")
                print(f"   📊 Results: {len(comments)} real user comments")
                print(f"   👥 Unique users: {unique_users}")
                print(f"   🔗 Profile links: {profile_links}")
                print(f"   🆔 UIDs extracted: {uid_count} ({uid_success_rate:.1f}% success rate)")
                print(f"   🚫 Anonymous users filtered: {anonymous_filtered}")
                print(f"   {mode_emoji} Mode: {mode_text}")
                print(f"   📱 Layout used: {layout}")
                print(f"   💾 Saved to: {file_out}")
                
            else:
                self.lbl_status.config(text="⚠️ Không tìm thấy comment với Enhanced UID logic", fg="#ffc107")
                self.lbl_progress_detail.config(text=f"💡 Layout: {layout} | Kiểm tra debug files để phân tích Facebook structure")
                
                print(f"⚠️ No comments found with Enhanced UID logic")
                print(f"   📱 Layout: {layout}")
                print(f"   🔍 Debug files created: debug_focused_{layout}.html")
                print(f"   💡 Suggestions:")
                print(f"      1. Check if you have access to the Facebook Group")
                print(f"      2. Verify the post URL is correct and public in the group")
                print(f"      3. Try running without headless mode to see what's happening")
                print(f"      4. Check the debug HTML file to understand the page structure")
                
        except Exception as e:
            error_msg = str(e)[:120]
            self.lbl_status.config(text=f"❌ Lỗi Enhanced UID scraping: {error_msg}...", fg="#dc3545")
            self.lbl_progress_detail.config(text="🔍 Xem console để biết chi tiết. Enhanced UID version cung cấp debug info.")
            print(f"Enhanced UID Groups scraping error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.progress_bar.stop()
            if self.scraper: 
                self.scraper.close()
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)

# ----------------------------
# Run Enhanced UID app
# ----------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = FBGroupsAppGUI(root)
    root.mainloop()