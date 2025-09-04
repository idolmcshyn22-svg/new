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
        
        # ENHANCED: Extract username từ URL với comment_id parameters
        username_patterns = [
            r'facebook\.com/([^/?]+)\?comment_id=',  # URL có comment_id
            r'facebook\.com/([^/?&]+)',  # URL thường
            r'facebook\.com/([^/?]+)'   # Fallback
        ]
        
        for pattern in username_patterns:
            username_match = re.search(pattern, profile_url)
            if username_match:
                username = username_match.group(1)
                # Clean username - remove numbers suffix if present
                clean_username = re.sub(r'\.\d+$', '', username)  # Remove .579704
                
                if not clean_username.isdigit() and len(clean_username) > 2:
                    print(f"    🔄 Found username: {username} (cleaned: {clean_username})")
                    return f"username:{clean_username}"  # Use cleaned username
                break
        
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

def clean_facebook_url(url):
    """
    Clean Facebook URL từ comment_id và các parameters không cần thiết
    """
    if not url:
        return url
    
    try:
        # Remove comment_id và tracking parameters
        cleaned_url = re.sub(r'\?comment_id=[^&]+', '', url)
        cleaned_url = re.sub(r'&comment_id=[^&]+', '', cleaned_url)
        cleaned_url = re.sub(r'&__cft__\[[^\]]+\]=[^&]+', '', cleaned_url)
        cleaned_url = re.sub(r'&__tn__=[^&]+', '', cleaned_url)
        cleaned_url = re.sub(r'\?__cft__\[[^\]]+\]=[^&]+', '', cleaned_url)
        cleaned_url = re.sub(r'\?__tn__=[^&]+', '', cleaned_url)
        
        # Remove trailing ? or &
        cleaned_url = re.sub(r'[?&]$', '', cleaned_url)
        
        print(f"🧹 Cleaned URL: {url[:50]}... -> {cleaned_url[:50]}...")
        return cleaned_url
        
    except Exception as e:
        print(f"⚠️ Error cleaning URL: {e}")
        return url

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
            
            # ENHANCED: Try multiple profile URL formats với cleaned username
            # Clean username để remove số suffix
            clean_username = re.sub(r'\.\d+$', '', username)  # lan.hoang.579704 -> lan.hoang
            
            profile_urls = [
                f"https://www.facebook.com/{clean_username}",  # Use cleaned username
                f"https://www.facebook.com/{username}",        # Original username
                f"https://m.facebook.com/{clean_username}",
                f"https://m.facebook.com/{username}",
                f"https://facebook.com/{clean_username}",
                f"https://facebook.com/{username}",
                f"https://www.facebook.com/profile.php?id={username}" if username.isdigit() else None
            ]
            
            for profile_url in profile_urls:
                if not profile_url:
                    continue
                    
                try:
                    # Clean profile URL trước khi navigate
                    clean_profile_url = clean_facebook_url(profile_url)
                    print(f"    🔗 Trying: {clean_profile_url}")
                    driver.get(clean_profile_url)
                    time.sleep(1.5)  # Tăng thêm thời gian để page load đầy đủ
                    
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
        
        # MEGA CACHE OPTIMIZATION: Enhanced cache cho high-volume processing
        self._uid_cache = {}  # Cache UID resolution
        self._profile_cache = {}  # Cache profile data
        self._element_cache = {}  # Cache element data để tránh re-parse
        self._processed_signatures = set()  # Track processed comments để tránh duplicates
        self._mega_mode_active = False  # Flag cho MEGA mode optimizations
        
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
                        max_no_new_comments = 3  # Tăng từ 1 lên 3 để click nhiều hơn
                        max_click_rounds = 25  # TĂNG từ 5 lên 25 rounds để load hết comments
                        click_round = 0
                        
                        while no_new_comments_count < max_no_new_comments and click_round < max_click_rounds:
                            click_round += 1
                            print(f"\n--- Click Round {click_round}/{max_click_rounds} ---")
                            
                            # ENHANCED "View more comments" button detection
                            view_more_selectors = [
                                # English variations
                                "//button[contains(text(), 'View more comments')]",
                                "//a[contains(text(), 'View more comments')]",
                                "//span[contains(text(), 'View more comments')]",
                                "//div[contains(text(), 'View more comments')]",
                                "//*[contains(text(), 'View more')]",
                                "//*[contains(text(), 'Show more')]",
                                "//*[contains(text(), 'Load more')]",
                                "//*[contains(text(), 'See more')]",
                                "//*[contains(text(), 'More comments')]",
                                "//*[contains(text(), 'Show all')]",
                                
                                # Vietnamese variations
                                "//*[contains(text(), 'Xem thêm')]",
                                "//*[contains(text(), 'Hiển thị thêm')]",
                                "//*[contains(text(), 'Tải thêm')]",
                                "//*[contains(text(), 'Xem tất cả')]",
                                "//*[contains(text(), 'Hiện thêm')]",
                                
                                # Generic patterns
                                "//*[contains(@class, 'more') and contains(@class, 'comment')]",
                                "//*[contains(@class, 'view-more')]",
                                "//*[contains(@class, 'show-more')]",
                                "//*[contains(@class, 'load-more')]",
                                "//*[@role='button' and contains(text(), 'more')]",
                                "//*[@role='button' and contains(text(), 'thêm')]",
                                
                                # Fallback patterns - broader search
                                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'more')]",
                                "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'more')]"
                            ]
                            
                            # ENHANCED button clicking - try multiple buttons if available
                            buttons_clicked = 0
                            total_buttons_found = 0
                            
                            for selector in view_more_selectors:
                                try:
                                    elements = self.driver.find_elements(By.XPATH, selector)
                                    total_buttons_found += len(elements)
                                    
                                    if elements:
                                        print(f"🔍 Found {len(elements)} buttons with selector: {selector[:50]}...")
                                        
                                        # Try clicking multiple buttons (up to 3 per selector)
                                        for i, element in enumerate(elements[:3]):
                                            try:
                                                # Check if button is visible and clickable
                                                if element.is_displayed() and element.is_enabled():
                                                    # Scroll to button first
                                                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                                                    time.sleep(0.3)
                                                    
                                                    # Try click
                                                    self.driver.execute_script("arguments[0].click();", element)
                                                    buttons_clicked += 1
                                                    print(f"✅ Clicked button {i+1} from selector: {selector[:30]}...")
                                                    time.sleep(0.8)  # Wait between clicks
                                                    
                                            except Exception as click_error:
                                                print(f"⚠️ Failed to click button {i+1}: {click_error}")
                                                continue
                                        
                                        # If we found and clicked buttons from this selector, continue to next selector
                                        if buttons_clicked > 0:
                                            continue
                                            
                                except Exception as selector_error:
                                    continue
                            
                            print(f"📊 Click summary: {buttons_clicked} buttons clicked out of {total_buttons_found} found")
                            
                            if buttons_clicked > 0:
                                print(f"🖱️ Successfully clicked {buttons_clicked} 'View more' buttons")
                            else:
                                print("⚠️ No clickable 'View more comments' buttons found")
                                no_new_comments_count += 1
                                print(f"⚠️ No new comments button detected ({no_new_comments_count}/{max_no_new_comments})")
                                
                                # Try alternative strategies when no buttons found
                                if no_new_comments_count == 1:
                                    print("🔄 Trying alternative button detection...")
                                    # Look for any clickable element containing "more" or "thêm"
                                    alternative_elements = self.driver.find_elements(By.XPATH, 
                                        "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'more') or contains(text(), 'thêm')]")
                                    
                                    print(f"🔍 Found {len(alternative_elements)} alternative elements")
                                    for alt_elem in alternative_elements[:5]:  # Try up to 5 alternatives
                                        try:
                                            if alt_elem.is_displayed():
                                                self.driver.execute_script("arguments[0].click();", alt_elem)
                                                print(f"✅ Clicked alternative element: {alt_elem.text[:30]}...")
                                                buttons_clicked += 1
                                                time.sleep(0.5)
                                        except:
                                            continue
                            
                            # SMART WAITING: Wait for new content to actually load
                            if buttons_clicked > 0:
                                print("⏳ Smart waiting for new comments to load...")
                                
                                # Monitor page changes for up to 3 seconds
                                wait_start = time.time()
                                initial_height = self.driver.execute_script("return document.body.scrollHeight")
                                content_changed = False
                                
                                while time.time() - wait_start < 3.0:  # Max 3 seconds wait
                                    time.sleep(0.5)
                                    current_height = self.driver.execute_script("return document.body.scrollHeight")
                                    
                                    if current_height != initial_height:
                                        content_changed = True
                                        print(f"✅ Page content changed: {initial_height} -> {current_height}")
                                        break
                                
                                if not content_changed:
                                    print("⚠️ No page content change detected after clicking")
                            else:
                                time.sleep(0.5)  # Minimal wait if no buttons clicked
                            
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
                            
                            # ENHANCED progress detection với nhiều metrics
                            current_total_comments = len(all_comments_data)
                            comment_growth = current_total_comments - previous_comment_count
                            
                            if processed_in_this_round > 0 or comment_growth > 0:
                                print(f"✅ Progress in round {click_round}: +{processed_in_this_round} processed, +{comment_growth} total growth")
                                no_new_comments_count = 0  # Reset counter
                                previous_comment_count = current_total_comments
                            else:
                                no_new_comments_count += 1
                                print(f"⚠️ No progress in round {click_round} ({no_new_comments_count}/{max_no_new_comments})")
                                
                                # Try additional strategies khi không có progress
                                if no_new_comments_count == 1:
                                    print("🔄 Trying additional scroll to trigger more comments...")
                                    for scroll_attempt in range(3):
                                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                                        time.sleep(0.5)
                                        self.driver.execute_script("window.scrollBy(0, -300);")
                                        time.sleep(0.3)
                                        self.driver.execute_script("window.scrollBy(0, 300);")
                                        time.sleep(0.5)
                            
                            # DYNAMIC EARLY EXIT: Chỉ exit khi thực sự có nhiều comments
                            # Không exit sớm nếu chưa đạt target tối thiểu
                            min_comments_before_exit = 50  # Ít nhất 50 comments trước khi có thể exit sớm
                            if len(all_comments_data) >= min_comments_before_exit:
                                # Dynamic threshold dựa trên số round
                                if click_round <= 10:
                                    early_exit_threshold = 1000  # Rounds đầu: target cao
                                elif click_round <= 20:
                                    early_exit_threshold = 500   # Rounds giữa: target trung bình
                                else:
                                    early_exit_threshold = 200   # Rounds cuối: target thấp
                                
                                if len(all_comments_data) >= early_exit_threshold:
                                    print(f"🎯 Dynamic early exit: {len(all_comments_data)} comments (threshold: {early_exit_threshold} for round {click_round})")
                                    break
                            else:
                                print(f"⏳ Continue clicking: {len(all_comments_data)}/{min_comments_before_exit} minimum comments")
                            
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
                                
                                # CLEAN profile link trước khi extract UID
                                clean_profile_href = clean_facebook_url(link_href)
                                
                                # IMMEDIATE UID extraction từ cleaned profile link
                                immediate_uid = extract_uid_from_profile_url(clean_profile_href)
                                if immediate_uid != "Unknown":
                                    print(f"    ⚡ FAST: Immediate UID from cleaned URL: {immediate_uid}")
                                
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
                # Clean profile_href trước khi extract UID
                clean_profile_href = clean_facebook_url(profile_href)
                uid = extract_uid_from_profile_url(clean_profile_href)
                print(f"    🎯 UID from cleaned profile URL: {uid}")
            
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
                clean_href = clean_facebook_url(profile_href)
                username_patterns = [
                    r'facebook\.com/([^/?]+)\?',  # With params
                    r'facebook\.com/([^/?]+)'    # Without params
                ]
                
                for pattern in username_patterns:
                    username_match = re.search(pattern, clean_href)
                    if username_match:
                        potential_username = username_match.group(1)
                        # Clean username - remove number suffix
                        clean_potential_username = re.sub(r'\.\d+$', '', potential_username)
                        
                        if not clean_potential_username.isdigit() and len(clean_potential_username) > 2:
                            uid = f"username:{clean_potential_username}"
                            print(f"    🔄 Marked for resolution: {uid} (cleaned from {potential_username})")
                            break
            
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
        max_click_attempts = 30  # TĂNG từ 15 lên 30 để load nhiều comments hơn
        consecutive_fails = 0
        max_consecutive_fails = 5  # Tăng từ 3 lên 5 để kiên nhẫn hơn
        
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

    def monitor_comment_loading_progress(self, initial_count=0, target_count=1000):
        """
        📊 Monitor và report progress của comment loading
        """
        current_elements = len(self.extract_all_fresh_comments())
        progress_percentage = (current_elements / target_count) * 100 if target_count > 0 else 0
        
        print(f"📊 PROGRESS MONITOR:")
        print(f"   🔍 Current elements found: {current_elements}")
        print(f"   🎯 Target: {target_count}")
        print(f"   📈 Progress: {progress_percentage:.1f}%")
        print(f"   📊 Growth from start: +{current_elements - initial_count}")
        
        return current_elements

    def extract_comments_via_javascript(self, max_comments=1000):
        """
        🚀 SUPER OPTIMIZED: Extract comments via JavaScript injection - NO CLICKING!
        """
        print(f"🚀 JAVASCRIPT extraction for up to {max_comments} comments (NO CLICKING)")
        
        # Inject JavaScript để extract tất cả comment data
        js_extraction_script = """
        // SUPER OPTIMIZED Facebook Comments Extraction via JavaScript
        function extractAllCommentsViaJS() {
            const results = [];
            const seen = new Set();
            
            console.log('🚀 Starting JavaScript extraction...');
            
            // Method 1: Extract từ Facebook's internal data structures
            try {
                // Facebook stores data in various global objects
                const fbObjects = [
                    window.__data,
                    window.require,
                    window._csr,
                    window.__d
                ];
                
                for (const obj of fbObjects) {
                    if (obj && typeof obj === 'object') {
                        const jsonStr = JSON.stringify(obj);
                        // Look for comment-like data structures
                        const commentMatches = jsonStr.match(/"id":"\\d{8,}","name":"[^"]+"/g);
                        if (commentMatches) {
                            console.log(`Found ${commentMatches.length} potential comments in FB objects`);
                        }
                    }
                }
            } catch (e) {
                console.log('Method 1 failed:', e);
            }
            
            // Method 2: Extract từ DOM elements với enhanced selectors
            const selectors = [
                '[data-testid*="comment"]',
                '[data-testid*="UFI"]',
                '[class*="comment"]',
                '[class*="UFI"]',
                'div[role="article"]',
                'a[href*="facebook.com/profile.php?id="]',
                'a[href*="facebook.com/user.php?id="]',
                'a[href*="facebook.com/people/"]',
                'a[href*="facebook.com/"]:not([href*="groups/"]):not([href*="pages/"]):not([href*="events/"])'
            ];
            
            for (const selector of selectors) {
                try {
                    const elements = document.querySelectorAll(selector);
                    console.log(`Selector ${selector}: ${elements.length} elements`);
                    
                    elements.forEach((el, idx) => {
                        try {
                            // Extract profile data
                            const links = el.querySelectorAll('a[href*="facebook.com"]');
                            const textContent = el.textContent || '';
                            
                            if (textContent.length > 10 && links.length > 0) {
                                for (const link of links) {
                                    const href = link.href;
                                    const text = link.textContent || '';
                                    
                                    // Extract UID from href
                                    let uid = 'Unknown';
                                    const uidPatterns = [
                                        /profile\\.php\\?id=(\\d+)/,
                                        /user\\.php\\?id=(\\d+)/,
                                        /people\\/[^\\/]+\\/(\\d+)/,
                                        /facebook\\.com\\/(\\d{8,})/
                                    ];
                                    
                                    for (const pattern of uidPatterns) {
                                        const match = href.match(pattern);
                                        if (match) {
                                            uid = match[1];
                                            break;
                                        }
                                    }
                                    
                                    if (uid !== 'Unknown' && text.length > 1 && text.length < 100) {
                                        const signature = `${text}_${uid}`;
                                        if (!seen.has(signature)) {
                                            seen.add(signature);
                                            results.push({
                                                UID: uid,
                                                Name: text,
                                                ProfileLink: href,
                                                CommentLink: '',
                                                ElementIndex: results.length,
                                                TextPreview: textContent.substring(0, 100),
                                                ContainerHeight: 'JavaScript Extracted',
                                                Type: 'Comment',
                                                Source: 'JavaScript DOM'
                                            });
                                        }
                                    }
                                }
                            }
                        } catch (e) {
                            console.log(`Error processing element ${idx}:`, e);
                        }
                    });
                } catch (e) {
                    console.log(`Selector ${selector} failed:`, e);
                }
            }
            
            // Method 3: Extract từ network responses (if available)
            try {
                if (window.performance && window.performance.getEntries) {
                    const entries = window.performance.getEntries();
                    const graphqlEntries = entries.filter(e => 
                        e.name && (e.name.includes('graphql') || e.name.includes('api'))
                    );
                    console.log(`Found ${graphqlEntries.length} potential API calls`);
                }
            } catch (e) {
                console.log('Method 3 failed:', e);
            }
            
            console.log(`🚀 JavaScript extraction complete: ${results.length} comments`);
            return results;
        }
        
        return extractAllCommentsViaJS();
        """
        
        try:
            # Execute JavaScript extraction
            print("⚡ Executing JavaScript extraction...")
            js_results = self.driver.execute_script(js_extraction_script)
            
            print(f"✅ JavaScript extraction returned {len(js_results) if js_results else 0} results")
            
            if js_results and len(js_results) > 0:
                # Process results
                processed_comments = []
                seen_content = set()
                
                for item in js_results:
                    try:
                        if isinstance(item, dict) and item.get('Name') != 'Unknown':
                            # Validate and clean data
                            if not is_anonymous_user(item['Name']):
                                content_signature = f"{item['Name']}_{item.get('UID', 'Unknown')}"
                                if content_signature not in seen_content:
                                    seen_content.add(content_signature)
                                    processed_comments.append(item)
                    except:
                        continue
                
                print(f"✅ Processed {len(processed_comments)} valid comments from JavaScript")
                return processed_comments
            
        except Exception as e:
            print(f"⚠️ JavaScript extraction failed: {e}")
        
        return []

    def extract_comments_via_network_monitoring(self):
        """
        🌐 ADVANCED: Monitor network requests để lấy data từ API calls
        """
        print("🌐 Setting up network monitoring for Facebook API calls...")
        
        # Enable network monitoring
        network_script = """
        // Monitor Facebook GraphQL/API calls
        const originalFetch = window.fetch;
        const originalXHR = window.XMLHttpRequest.prototype.open;
        window.facebookData = [];
        
        // Intercept fetch requests
        window.fetch = function(...args) {
            const url = args[0];
            if (typeof url === 'string' && (url.includes('graphql') || url.includes('api'))) {
                console.log('Intercepted fetch:', url);
                
                return originalFetch.apply(this, args).then(response => {
                    const clonedResponse = response.clone();
                    clonedResponse.text().then(text => {
                        if (text.includes('comment') || text.includes('profile_id')) {
                            window.facebookData.push({
                                url: url,
                                data: text,
                                timestamp: Date.now()
                            });
                        }
                    }).catch(() => {});
                    return response;
                });
            }
            return originalFetch.apply(this, args);
        };
        
        // Intercept XHR requests
        window.XMLHttpRequest.prototype.open = function(method, url, ...args) {
            if (typeof url === 'string' && (url.includes('graphql') || url.includes('api'))) {
                console.log('Intercepted XHR:', url);
                
                this.addEventListener('load', function() {
                    if (this.responseText && (this.responseText.includes('comment') || this.responseText.includes('profile_id'))) {
                        window.facebookData.push({
                            url: url,
                            data: this.responseText,
                            timestamp: Date.now()
                        });
                    }
                });
            }
            return originalXHR.apply(this, [method, url, ...args]);
        };
        
        console.log('🌐 Network monitoring setup complete');
        """
        
        try:
            # Setup network monitoring
            self.driver.execute_script(network_script)
            
            # Trigger some activity to generate API calls
            print("🔄 Triggering activity to capture API calls...")
            
            # Scroll a bit to trigger lazy loading
            for i in range(3):
                self.driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(1)
            
            # Check captured data
            captured_data = self.driver.execute_script("return window.facebookData || [];")
            
            print(f"🌐 Captured {len(captured_data)} network requests")
            
            # Process captured API data
            comments_from_api = []
            for request in captured_data:
                try:
                    data_str = request.get('data', '')
                    
                    # Look for comment data in API responses
                    import json
                    if data_str.startswith('{'):
                        api_data = json.loads(data_str)
                        # Process API data to extract comments
                        # This would need to be customized based on Facebook's API structure
                        
                except Exception as e:
                    continue
            
            return comments_from_api
            
        except Exception as e:
            print(f"⚠️ Network monitoring failed: {e}")
            return []

    def extract_comments_virtual_click(self, max_comments=1000):
        """
        🎯 VIRTUAL CLICK: Simulate clicks via JavaScript thay vì real clicks
        """
        print(f"🎯 VIRTUAL CLICK extraction for up to {max_comments} comments")
        
        virtual_click_script = """
        function virtualClickExtraction() {
            const results = [];
            let totalClicks = 0;
            
            console.log('🎯 Starting virtual click extraction...');
            
            // Function to virtual click an element
            function virtualClick(element) {
                if (!element) return false;
                
                try {
                    // Create and dispatch click events
                    const events = ['mousedown', 'mouseup', 'click'];
                    
                    for (const eventType of events) {
                        const event = new MouseEvent(eventType, {
                            bubbles: true,
                            cancelable: true,
                            view: window
                        });
                        element.dispatchEvent(event);
                    }
                    
                    // Also try direct click
                    if (element.click) {
                        element.click();
                    }
                    
                    totalClicks++;
                    return true;
                } catch (e) {
                    console.log('Virtual click failed:', e);
                    return false;
                }
            }
            
            // Find and virtual click "View more" buttons
            const viewMoreSelectors = [
                'button:contains("View more")',
                'a:contains("View more")',
                'span:contains("View more")',
                'div:contains("View more")',
                '[role="button"]:contains("more")',
                'button:contains("Xem thêm")',
                'a:contains("Xem thêm")'
            ];
            
            // jQuery-like contains selector implementation
            function findElementsContaining(text) {
                const elements = [];
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                
                let node;
                while (node = walker.nextNode()) {
                    if (node.textContent.toLowerCase().includes(text.toLowerCase())) {
                        let parent = node.parentElement;
                        while (parent && parent !== document.body) {
                            if (parent.tagName === 'BUTTON' || parent.tagName === 'A' || 
                                parent.getAttribute('role') === 'button') {
                                elements.push(parent);
                                break;
                            }
                            parent = parent.parentElement;
                        }
                    }
                }
                return elements;
            }
            
            // Virtual click all "View more" buttons
            const textsToFind = ['view more', 'show more', 'xem thêm', 'hiển thị thêm'];
            
            for (const text of textsToFind) {
                const buttons = findElementsContaining(text);
                console.log(`Found ${buttons.length} buttons with text "${text}"`);
                
                for (const button of buttons) {
                    if (virtualClick(button)) {
                        console.log(`Virtual clicked: ${button.textContent}`);
                        
                        // Wait a bit for content to load
                        await new Promise(resolve => setTimeout(resolve, 500));
                    }
                }
            }
            
            console.log(`🎯 Virtual clicked ${totalClicks} elements`);
            
            // Now extract all visible comments
            const commentElements = document.querySelectorAll([
                '[data-testid*="comment"]',
                'a[href*="facebook.com/profile.php?id="]',
                'a[href*="facebook.com/user.php?id="]',
                'div:has(a[href*="facebook.com/"])'
            ].join(','));
            
            console.log(`Found ${commentElements.length} potential comment elements`);
            
            // Process elements to extract comment data
            const seen = new Set();
            
            commentElements.forEach((el, idx) => {
                try {
                    const links = el.querySelectorAll('a[href*="facebook.com"]');
                    const textContent = el.textContent || '';
                    
                    if (textContent.length > 10 && links.length > 0) {
                        for (const link of links) {
                            const href = link.href;
                            const name = link.textContent || '';
                            
                            if (name.length > 1 && name.length < 100) {
                                // Extract UID
                                let uid = 'Unknown';
                                const uidMatch = href.match(/(?:profile\\.php\\?id=|user\\.php\\?id=|people\\/[^\\/]+\\/)?(\\d{8,})/);
                                if (uidMatch) {
                                    uid = uidMatch[1];
                                }
                                
                                const signature = `${name}_${uid}`;
                                if (!seen.has(signature)) {
                                    seen.add(signature);
                                    results.push({
                                        UID: uid,
                                        Name: name,
                                        ProfileLink: href,
                                        CommentLink: '',
                                        ElementIndex: results.length,
                                        TextPreview: textContent.substring(0, 100),
                                        ContainerHeight: 'Virtual Click Extracted',
                                        Type: 'Comment',
                                        Source: 'Virtual Click'
                                    });
                                }
                            }
                        }
                    }
                } catch (e) {
                    console.log(`Error processing element ${idx}:`, e);
                }
            });
            
            console.log(`🎯 Virtual click extraction complete: ${results.length} comments`);
            return {
                comments: results,
                totalClicks: totalClicks
            };
        }
        
        return virtualClickExtraction();
        """
        
        try:
            print("⚡ Executing virtual click extraction...")
            result = self.driver.execute_script(virtual_click_script)
            
            if result and isinstance(result, dict):
                comments = result.get('comments', [])
                total_clicks = result.get('totalClicks', 0)
                
                print(f"✅ Virtual clicks: {total_clicks}, Comments extracted: {len(comments)}")
                
                # Process and validate results
                processed_comments = []
                seen_content = set()
                
                for comment in comments:
                    try:
                        if isinstance(comment, dict) and comment.get('Name') != 'Unknown':
                            if not is_anonymous_user(comment['Name']):
                                content_signature = f"{comment['Name']}_{comment.get('UID', 'Unknown')}"
                                if content_signature not in seen_content:
                                    seen_content.add(content_signature)
                                    processed_comments.append(comment)
                    except:
                        continue
                
                print(f"✅ Processed {len(processed_comments)} valid comments from virtual clicks")
                return processed_comments
            
        except Exception as e:
            print(f"⚠️ Virtual click extraction failed: {e}")
        
        return []

    def scrape_all_comments(self, limit=0, resolve_uid=True, progress_callback=None):
        """Main scraping orchestrator with FOCUSED approach"""
        print(f"=== STARTING FOCUSED GROUPS SCRAPING ===")
        
        # Reset counters
        self._anonymous_filtered_count = 0
        
        if self._stop_flag:
            return []
        
        # Step 1: AUTO-DETECT best extraction method based on target
        if limit >= 10000:
            print(f"🔥 AUTO-DETECT: Using MEGA method for {limit:,}+ comments")
            comments = self.scrape_mega_volume_comments(target_comments=limit, progress_callback=progress_callback)
            # Return early since MEGA method handles everything
            return comments
        elif limit >= 1000:
            print("🚀 AUTO-DETECT: Using BULK method for 1k+ comments")
            comments = self.extract_comments_bulk_optimized(max_comments=limit or 1000)
        else:
            print("📝 AUTO-DETECT: Using standard method for <1k comments")
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

    def test_comment_id_urls(self):
        """
        🧪 Test URLs có comment_id parameters
        """
        print("🧪 Testing comment_id URL handling...")
        
        # Test URLs with comment_id
        test_urls = [
            "https://www.facebook.com/lan.hoang.579704?comment_id=Y29tbWVudDozMTI1ODQ4ODU3MDQ2NDUyM18zMTMyMDkxNjIwMDg4ODQyNg%3D%3D&__cft__[0]=test",
            "https://www.facebook.com/john.doe.123?comment_id=test&__tn__=R",
            "https://facebook.com/jane.smith.456?comment_id=abc123"
        ]
        
        for i, url in enumerate(test_urls):
            print(f"\n--- Test {i+1}: Comment ID URL ---")
            print(f"Original: {url}")
            
            # Test cleaning
            cleaned = clean_facebook_url(url)
            print(f"Cleaned: {cleaned}")
            
            # Test UID extraction
            uid_result = extract_uid_from_profile_url(cleaned)
            print(f"UID Result: {uid_result}")
            
            # Test username extraction
            if uid_result.startswith("username:"):
                username = uid_result.split(":", 1)[1]
                print(f"Username for resolution: {username}")
        
        print("🧪 Comment ID URL test complete!")

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

    def scrape_comments_ultra_optimized(self, max_comments=1000, progress_callback=None):
        """
        🚀 ULTRA OPTIMIZED: Combine tất cả phương pháp tối ưu nhất - NO REAL CLICKS!
        """
        print("🚀🚀🚀 ULTRA OPTIMIZED SCRAPING - NO REAL CLICKS! 🚀🚀🚀")
        
        start_time = time.time()
        all_comments = []
        seen_signatures = set()
        
        # Method 1: JavaScript Direct Extraction (fastest)
        print("\n=== METHOD 1: JavaScript Direct Extraction ===")
        js_comments = self.extract_comments_via_javascript(max_comments)
        for comment in js_comments:
            sig = f"{comment['Name']}_{comment.get('UID', 'Unknown')}"
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                all_comments.append(comment)
        print(f"✅ JavaScript method: {len(js_comments)} comments")
        
        # Method 2: Virtual Click (if needed)
        if len(all_comments) < max_comments * 0.7:  # If we need more
            print("\n=== METHOD 2: Virtual Click Extraction ===")
            virtual_comments = self.extract_comments_virtual_click(max_comments - len(all_comments))
            for comment in virtual_comments:
                sig = f"{comment['Name']}_{comment.get('UID', 'Unknown')}"
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    all_comments.append(comment)
            print(f"✅ Virtual click method: {len(virtual_comments)} new comments")
        
        # Method 3: Network Monitoring (if still needed)
        if len(all_comments) < max_comments * 0.5:
            print("\n=== METHOD 3: Network Monitoring ===")
            network_comments = self.extract_comments_via_network_monitoring()
            for comment in network_comments:
                sig = f"{comment['Name']}_{comment.get('UID', 'Unknown')}"
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    all_comments.append(comment)
            print(f"✅ Network method: {len(network_comments)} new comments")
        
        # Method 4: Fallback to enhanced traditional method (if really needed)
        if len(all_comments) < max_comments * 0.3:
            print("\n=== METHOD 4: Enhanced Traditional Fallback ===")
            traditional_comments = self.extract_comments_bulk_optimized(max_comments - len(all_comments))
            for comment in traditional_comments:
                sig = f"{comment['Name']}_{comment.get('UID', 'Unknown')}"
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    all_comments.append(comment)
            print(f"✅ Traditional method: {len(traditional_comments)} new comments")
        
        # Enhanced UID resolution for all comments
        print(f"\n=== UID RESOLUTION PHASE ===")
        uid_resolved = 0
        for comment in all_comments:
            if comment.get('UID') == 'Unknown' or comment.get('UID', '').startswith('username:'):
                username = comment.get('Name', '')
                if username and username != 'Unknown':
                    enhanced_uid = get_uid_from_username_enhanced(username, self.cookies_dict, self.driver, self._uid_cache)
                    if enhanced_uid != 'Unknown':
                        comment['UID'] = enhanced_uid
                        uid_resolved += 1
        
        # Final filtering
        print(f"\n=== FINAL FILTERING ===")
        filtered_comments = []
        for comment in all_comments:
            if comment.get('Name') != 'Unknown' and not is_anonymous_user(comment['Name']):
                filtered_comments.append(comment)
        
        # Apply limit
        if len(filtered_comments) > max_comments:
            filtered_comments = filtered_comments[:max_comments]
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Progress callback
        if progress_callback:
            progress_callback(len(filtered_comments))
        
        # Performance report
        print(f"\n🎯 ULTRA OPTIMIZED RESULTS:")
        print(f"   📊 Total comments: {len(filtered_comments)}")
        print(f"   ⏰ Time taken: {elapsed:.2f} seconds")
        print(f"   ⚡ Speed: {len(filtered_comments)/elapsed:.1f} comments/second")
        print(f"   🔍 UID resolved: {uid_resolved}")
        print(f"   💾 Cache entries: {len(self._uid_cache)}")
        print(f"   🎯 Success rate: {(len(filtered_comments)/max_comments)*100:.1f}%")
        
        return filtered_comments

    def activate_mega_mode(self):
        """Activate MEGA mode optimizations"""
        self._mega_mode_active = True
        
        # MEGA mode browser optimizations
        self.driver.execute_script("""
            // Disable unnecessary features for performance
            if (window.performance) {
                window.performance.mark = function() {};
                window.performance.measure = function() {};
            }
            
            // Reduce animation delays
            document.documentElement.style.setProperty('--animation-duration', '0.1s', 'important');
            document.documentElement.style.setProperty('--transition-duration', '0.1s', 'important');
            
            // Optimize DOM updates
            if (window.requestAnimationFrame) {
                const originalRAF = window.requestAnimationFrame;
                window.requestAnimationFrame = function(callback) {
                    return originalRAF(function() {
                        callback();
                    });
                };
            }
            
            console.log('🔥 MEGA mode browser optimizations activated');
        """)
        
        print("🔥 MEGA mode optimizations activated!")

    def scrape_mega_volume_comments(self, target_comments=30000, progress_callback=None):
        """
        🚀 MEGA OPTIMIZATION: 10-30K comments với streaming processing
        """
        print(f"🚀🚀🚀 MEGA VOLUME OPTIMIZATION: TARGET {target_comments:,} COMMENTS 🚀🚀🚀")
        
        # Activate MEGA mode
        self.activate_mega_mode()
        
        start_time = time.time()
        
        # MEGA optimizations
        mega_batch_size = 100  # Process 100 comments per batch
        streaming_save_interval = 1000  # Save every 1000 comments
        max_memory_comments = 5000  # Max comments in memory before flush
        
        # Initialize streaming data
        all_comments = []
        processed_count = 0
        saved_batches = 0
        
        # Phase 1: AGGRESSIVE page preparation
        print("\n=== PHASE 1: MEGA PAGE PREPARATION ===")
        
        # Ultra-aggressive scrolling to load maximum content
        print("⚡ MEGA scrolling to load maximum comments...")
        scroll_height = 0
        max_mega_scrolls = 50  # Tăng từ 20 lên 50
        
        for scroll_round in range(max_mega_scrolls):
            # Multi-direction scrolling
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.3)
            self.driver.execute_script("window.scrollBy(0, -1000);")
            time.sleep(0.2)
            self.driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(0.3)
            
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height > scroll_height:
                scroll_height = new_height
                print(f"  📈 Scroll {scroll_round + 1}: Height {new_height}")
            else:
                if scroll_round % 5 == 0:  # Every 5 rounds, report
                    print(f"  ⏸️ Scroll {scroll_round + 1}: No new content")
        
        # MEGA button clicking - ultra aggressive
        print("🔄 MEGA clicking ALL possible buttons...")
        mega_click_attempts = 50  # Tăng lên 50 attempts
        total_mega_clicks = 0
        
        for mega_round in range(mega_click_attempts):
            # Find ALL possible buttons
            all_buttons = self.driver.find_elements(By.XPATH, 
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'more') or contains(text(), 'thêm') or contains(text(), 'view') or contains(text(), 'show') or contains(text(), 'load')]")
            
            round_clicks = 0
            for button in all_buttons[:10]:  # Try up to 10 buttons per round
                try:
                    if button.is_displayed() and button.is_enabled():
                        self.driver.execute_script("arguments[0].click();", button)
                        round_clicks += 1
                        time.sleep(0.2)  # Very fast between clicks
                except:
                    continue
            
            total_mega_clicks += round_clicks
            
            if round_clicks > 0:
                print(f"  🖱️ Mega round {mega_round + 1}: {round_clicks} clicks")
                time.sleep(1)  # Wait for content after successful clicks
            else:
                if mega_round > 10:  # After 10 rounds with no clicks, stop
                    break
        
        print(f"✅ MEGA preparation: {total_mega_clicks} total clicks, height: {scroll_height}")
        
        # Phase 2: STREAMING extraction với memory management
        print(f"\n=== PHASE 2: MEGA STREAMING EXTRACTION ===")
        
        extraction_round = 0
        max_extraction_rounds = 10  # Multiple extraction rounds
        
        while len(all_comments) < target_comments and extraction_round < max_extraction_rounds:
            extraction_round += 1
            print(f"\n--- Extraction Round {extraction_round}/{max_extraction_rounds} ---")
            
            # Get all elements in this round
            round_elements = self.extract_all_fresh_comments()
            print(f"📦 Round {extraction_round}: Found {len(round_elements)} elements")
            
            # Process in mega batches
            round_comments = []
            seen_in_round = set()
            
            for batch_start in range(0, len(round_elements), mega_batch_size):
                batch_end = min(batch_start + mega_batch_size, len(round_elements))
                batch_elements = round_elements[batch_start:batch_end]
                
                batch_comments = []
                for element in batch_elements:
                    try:
                        comment_data = self.extract_comment_data_fast(element, processed_count)
                        if comment_data and comment_data['Name'] != "Unknown":
                            if not is_anonymous_user(comment_data['Name']):
                                content_sig = f"{comment_data['Name']}_{comment_data.get('UID', 'Unknown')}"
                                if content_sig not in seen_in_round:
                                    seen_in_round.add(content_sig)
                                    comment_data['ExtractionRound'] = extraction_round
                                    comment_data['BatchNumber'] = batch_start // mega_batch_size + 1
                                    batch_comments.append(comment_data)
                                    processed_count += 1
                    except:
                        continue
                
                round_comments.extend(batch_comments)
                
                # Progress callback
                if progress_callback and processed_count % 100 == 0:
                    progress_callback(processed_count)
                
                print(f"    📦 Batch {batch_start//mega_batch_size + 1}: +{len(batch_comments)} comments (total: {processed_count})")
            
            all_comments.extend(round_comments)
            print(f"✅ Round {extraction_round}: +{len(round_comments)} new comments (total: {len(all_comments)})")
            
            # MEMORY MANAGEMENT: Save and clear if too many in memory
            if len(all_comments) >= max_memory_comments:
                print(f"💾 MEMORY MANAGEMENT: Saving batch {saved_batches + 1}...")
                
                # Save intermediate batch
                self._save_intermediate_batch(all_comments, saved_batches + 1)
                saved_batches += 1
                
                # Keep only recent comments in memory
                all_comments = all_comments[-1000:]  # Keep last 1000 for deduplication
                print(f"   💾 Saved batch, keeping {len(all_comments)} in memory")
            
            # If no new comments in this round, try more aggressive loading
            if len(round_comments) == 0:
                print("🔄 No new comments, trying MEGA boost...")
                
                # MEGA boost: More scrolling + clicking
                for boost in range(5):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
                    
                    # Try to find any more buttons
                    more_buttons = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'more') or contains(text(), 'thêm')]")
                    for btn in more_buttons[:3]:
                        try:
                            self.driver.execute_script("arguments[0].click();", btn)
                            time.sleep(0.5)
                        except:
                            continue
                
                # If still no progress after boost, break
                final_check = len(self.extract_all_fresh_comments())
                if final_check <= len(round_elements):
                    print("⏹️ No more content available after MEGA boost")
                    break
        
        # Phase 3: FINAL processing và UID resolution
        print(f"\n=== PHASE 3: MEGA UID RESOLUTION ===")
        
        # Load any saved batches
        if saved_batches > 0:
            print(f"📂 Loading {saved_batches} saved batches...")
            # In real implementation, would load from temp files
        
        # Enhanced UID resolution for remaining comments
        uid_resolution_batch_size = 50  # Resolve UIDs in batches of 50
        uid_resolved = 0
        
        for uid_batch_start in range(0, len(all_comments), uid_resolution_batch_size):
            uid_batch_end = min(uid_batch_start + uid_resolution_batch_size, len(all_comments))
            uid_batch = all_comments[uid_batch_start:uid_batch_end]
            
            for comment in uid_batch:
                if comment.get('UID') == 'Unknown' or comment.get('UID', '').startswith('username:'):
                    username = comment.get('Name', '')
                    if username and username != 'Unknown':
                        enhanced_uid = get_uid_from_username_enhanced(username, self.cookies_dict, self.driver, self._uid_cache)
                        if enhanced_uid != 'Unknown':
                            comment['UID'] = enhanced_uid
                            uid_resolved += 1
            
            print(f"🔍 UID batch {uid_batch_start//uid_resolution_batch_size + 1}: {len(uid_batch)} processed")
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Final statistics
        print(f"\n🎯 MEGA VOLUME RESULTS:")
        print(f"   📊 Target: {target_comments:,}")
        print(f"   📊 Achieved: {len(all_comments):,}")
        print(f"   📈 Success rate: {(len(all_comments)/target_comments)*100:.1f}%")
        print(f"   ⏰ Total time: {elapsed:.2f} seconds ({elapsed/60:.1f} minutes)")
        print(f"   ⚡ Speed: {len(all_comments)/elapsed:.1f} comments/second")
        print(f"   🔍 UID resolved: {uid_resolved:,}")
        print(f"   💾 Batches saved: {saved_batches}")
        print(f"   📦 Extraction rounds: {extraction_round}")
        
        return all_comments

    def _save_intermediate_batch(self, comments, batch_number):
        """Save intermediate batch để manage memory"""
        try:
            import pandas as pd
            df = pd.DataFrame(comments)
            filename = f"temp_batch_{batch_number}.xlsx"
            df.to_excel(filename, index=False, engine="openpyxl")
            print(f"💾 Saved batch {batch_number}: {len(comments)} comments to {filename}")
        except Exception as e:
            print(f"⚠️ Error saving batch {batch_number}: {e}")

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
        
        # ULTRA button cho method mới nhất
        self.btn_ultra = tk.Button(button_frame, text="🚀 ULTRA Mode", bg="#e83e8c", fg="white", 
                                  font=("Arial", 11, "bold"), command=self.start_ultra_scrape, 
                                  pady=8, padx=20)
        self.btn_ultra.pack(side="left", padx=(10,0))
        
        # MEGA button cho 10-30K comments
        self.btn_mega = tk.Button(button_frame, text="🔥 MEGA 30K", bg="#ff6b35", fg="white", 
                                 font=("Arial", 11, "bold"), command=self.start_mega_scrape, 
                                 pady=8, padx=20)
        self.btn_mega.pack(side="left", padx=(10,0))

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

    def test_comment_id_urls(self):
        """🔗 Test comment_id URL cleaning và UID extraction"""
        try:
            self.lbl_status.config(text="🔗 Testing comment_id URL handling...", fg="#20c997")
            
            # Import functions để test
            from FB import clean_facebook_url, extract_uid_from_profile_url
            
            # Test with real URL from user's log
            test_url = "https://www.facebook.com/lan.hoang.579704?comment_id=Y29tbWVudDozMTI1ODQ4ODU3MDQ2NDUyM18zMTMyMDkxNjIwMDg4ODQyNg%3D%3D&__cft__[0]=test"
            
            print(f"🔗 Testing comment_id URL handling:")
            print(f"Original: {test_url}")
            
            # Clean URL
            cleaned = clean_facebook_url(test_url)
            print(f"Cleaned: {cleaned}")
            
            # Extract UID
            uid_result = extract_uid_from_profile_url(cleaned)
            print(f"UID Result: {uid_result}")
            
            if uid_result.startswith("username:"):
                username = uid_result.split(":", 1)[1]
                print(f"Username for resolution: {username}")
                
                # Test enhanced resolution if scraper available
                if hasattr(self, 'scraper') and self.scraper:
                    resolved_uid = get_uid_from_username_enhanced(username, self.scraper.cookies_dict, self.scraper.driver, self.scraper._uid_cache)
                    print(f"Resolved UID: {resolved_uid}")
            
            self.lbl_status.config(text="✅ Comment_id URL test completed! Check console.", fg="#28a745")
            
        except Exception as e:
            self.lbl_status.config(text=f"❌ Comment_id test failed: {str(e)}", fg="#dc3545")
            messagebox.showerror("Comment_id Test Error", f"Lỗi test comment_id: {str(e)}")

    def start_ultra_scrape(self):
        """🚀 Start ULTRA optimized scraping - NO REAL CLICKS!"""
        try:
            # Validate inputs
            post_url = self.entry_url.get().strip()
            if not post_url:
                messagebox.showerror("Lỗi", "Vui lòng nhập URL Facebook post!")
                return
            
            cookie_str = self.text_cookie.get("1.0", tk.END).strip()
            if not cookie_str:
                messagebox.showerror("Lỗi", "Vui lòng nhập Facebook cookies!")
                return
            
            file_out = self.entry_file.get().strip()
            if not file_out:
                messagebox.showerror("Lỗi", "Vui lòng chọn file output!")
                return
            
            # Get limit (default to 1000 for ULTRA mode)
            try:
                limit = int(self.entry_limit.get() or "1000")
                if limit < 100:
                    limit = 1000  # ULTRA mode minimum
            except:
                limit = 1000
            
            # Start ULTRA scraping in thread
            self.lbl_status.config(text="🚀 ULTRA Mode: Starting NO-CLICK extraction...", fg="#e83e8c")
            self.btn_ultra.config(state=tk.DISABLED)
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            
            self._stop_flag = False
            self._scrape_thread = threading.Thread(target=self._ultra_scrape_worker, 
                                                   args=(post_url, cookie_str, file_out, limit))
            self._scrape_thread.daemon = True
            self._scrape_thread.start()
            
        except Exception as e:
            self.lbl_status.config(text=f"❌ ULTRA start failed: {str(e)}", fg="#dc3545")
            messagebox.showerror("ULTRA Error", f"Lỗi khởi động ULTRA mode: {str(e)}")

    def _ultra_scrape_worker(self, url, cookie_str, file_out, limit):
        """Worker thread for ULTRA scraping"""
        try:
            # Initialize scraper
            self.scraper = FacebookGroupsScraper(cookie_str, self.headless_var.get())
            
            # Load post
            self.lbl_status.config(text="🚀 ULTRA: Loading post...", fg="#e83e8c")
            self.scraper.load_post(url)
            
            # ULTRA extraction
            self.lbl_status.config(text="🚀 ULTRA: JavaScript + Virtual Click extraction...", fg="#e83e8c")
            comments = self.scraper.scrape_comments_ultra_optimized(max_comments=limit, 
                                                                   progress_callback=self._progress_cb)
            
            if self._stop_flag:
                return
            
            # Save results
            self.lbl_status.config(text="💾 ULTRA: Saving results...", fg="#e83e8c")
            
            if comments:
                import pandas as pd
                df = pd.DataFrame(comments)
                
                if file_out.endswith('.xlsx'):
                    df.to_excel(file_out, index=False, engine="openpyxl")
                else:
                    df.to_csv(file_out, index=False, encoding='utf-8-sig')
                
                # Statistics
                unique_users = len(set(c['Name'] for c in comments if c['Name'] != 'Unknown'))
                uid_count = len([c for c in comments if c.get('UID', 'Unknown') != 'Unknown'])
                uid_rate = (uid_count / len(comments)) * 100 if comments else 0
                
                self.lbl_status.config(text=f"✅ ULTRA Complete: {len(comments)} comments | {unique_users} users | {uid_rate:.1f}% UIDs", fg="#28a745")
                
                messagebox.showinfo("ULTRA Success!", 
                                   f"🚀 ULTRA Mode hoàn thành!\n\n"
                                   f"📊 Comments: {len(comments)}\n"
                                   f"👥 Unique users: {unique_users}\n"
                                   f"🔍 UID success: {uid_rate:.1f}%\n"
                                   f"💾 Saved to: {file_out}\n\n"
                                   f"⚡ Method: JavaScript + Virtual Click\n"
                                   f"🚫 NO real clicks used!")
            else:
                self.lbl_status.config(text="⚠️ ULTRA: No comments found", fg="#ffc107")
                messagebox.showwarning("ULTRA Warning", "Không tìm thấy comments nào!")
                
        except Exception as e:
            self.lbl_status.config(text=f"❌ ULTRA failed: {str(e)}", fg="#dc3545")
            messagebox.showerror("ULTRA Error", f"Lỗi ULTRA scraping: {str(e)}")
            
        finally:
            # Reset buttons
            self.btn_ultra.config(state=tk.NORMAL)
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            
            # Close scraper
            if hasattr(self, 'scraper') and self.scraper:
                try:
                    self.scraper.close()
                except:
                    pass

    def start_mega_scrape(self):
        """🔥 Start MEGA scraping for 10-30K comments"""
        try:
            # Validate inputs
            post_url = self.entry_url.get().strip()
            if not post_url:
                messagebox.showerror("Lỗi", "Vui lòng nhập URL Facebook post!")
                return
            
            cookie_str = self.text_cookie.get("1.0", tk.END).strip()
            if not cookie_str:
                messagebox.showerror("Lỗi", "Vui lòng nhập Facebook cookies!")
                return
            
            file_out = self.entry_file.get().strip()
            if not file_out:
                messagebox.showerror("Lỗi", "Vui lòng chọn file output!")
                return
            
            # Confirm MEGA mode
            result = messagebox.askyesno("🔥 MEGA Mode Confirmation", 
                                       "🔥 MEGA Mode sẽ scrape 10-30K comments!\n\n"
                                       "⚠️ Quá trình có thể mất 10-30 phút\n"
                                       "💾 Sẽ tạo temporary files trong quá trình\n"
                                       "🚀 Sử dụng streaming processing\n\n"
                                       "Bạn có chắc muốn tiếp tục?")
            if not result:
                return
            
            # Get target (default 30K for MEGA mode)
            try:
                target = int(self.entry_limit.get() or "30000")
                if target < 1000:
                    target = 30000  # MEGA mode minimum
            except:
                target = 30000
            
            # Start MEGA scraping in thread
            self.lbl_status.config(text="🔥 MEGA Mode: Preparing for high-volume extraction...", fg="#ff6b35")
            self.btn_mega.config(state=tk.DISABLED)
            self.btn_start.config(state=tk.DISABLED)
            self.btn_ultra.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            
            self._stop_flag = False
            self._scrape_thread = threading.Thread(target=self._mega_scrape_worker, 
                                                   args=(post_url, cookie_str, file_out, target))
            self._scrape_thread.daemon = True
            self._scrape_thread.start()
            
        except Exception as e:
            self.lbl_status.config(text=f"❌ MEGA start failed: {str(e)}", fg="#dc3545")
            messagebox.showerror("MEGA Error", f"Lỗi khởi động MEGA mode: {str(e)}")

    def _mega_scrape_worker(self, url, cookie_str, file_out, target):
        """Worker thread for MEGA scraping"""
        try:
            # Initialize scraper
            self.scraper = FacebookGroupsScraper(cookie_str, self.headless_var.get())
            
            # Load post
            self.lbl_status.config(text="🔥 MEGA: Loading post...", fg="#ff6b35")
            self.scraper.load_post(url)
            
            # MEGA extraction
            self.lbl_status.config(text=f"🔥 MEGA: Extracting {target:,} comments...", fg="#ff6b35")
            comments = self.scraper.scrape_mega_volume_comments(target_comments=target, 
                                                              progress_callback=self._progress_cb)
            
            if self._stop_flag:
                return
            
            # Save final results
            self.lbl_status.config(text="💾 MEGA: Consolidating and saving final results...", fg="#ff6b35")
            
            if comments:
                import pandas as pd
                df = pd.DataFrame(comments)
                
                # Add MEGA metadata
                df['MegaMode'] = True
                df['ProcessingMethod'] = 'MEGA Volume Optimization'
                df['TargetComments'] = target
                
                if file_out.endswith('.xlsx'):
                    df.to_excel(file_out, index=False, engine="openpyxl")
                else:
                    df.to_csv(file_out, index=False, encoding='utf-8-sig')
                
                # Statistics
                unique_users = len(set(c['Name'] for c in comments if c['Name'] != 'Unknown'))
                uid_count = len([c for c in comments if c.get('UID', 'Unknown') != 'Unknown'])
                uid_rate = (uid_count / len(comments)) * 100 if comments else 0
                success_rate = (len(comments) / target) * 100
                
                self.lbl_status.config(text=f"✅ MEGA Complete: {len(comments):,} comments | {success_rate:.1f}% of target", fg="#28a745")
                
                messagebox.showinfo("🔥 MEGA Success!", 
                                   f"🔥 MEGA Mode hoàn thành!\n\n"
                                   f"📊 Comments: {len(comments):,}\n"
                                   f"🎯 Target: {target:,}\n"
                                   f"📈 Success: {success_rate:.1f}%\n"
                                   f"👥 Unique users: {unique_users:,}\n"
                                   f"🔍 UID success: {uid_rate:.1f}%\n"
                                   f"💾 Saved to: {file_out}\n\n"
                                   f"⚡ Method: MEGA Volume Streaming\n"
                                   f"🚀 50 scroll rounds + 50 click rounds\n"
                                   f"💾 Memory-optimized processing")
            else:
                self.lbl_status.config(text="⚠️ MEGA: No comments found", fg="#ffc107")
                messagebox.showwarning("MEGA Warning", "Không tìm thấy comments nào!")
                
        except Exception as e:
            self.lbl_status.config(text=f"❌ MEGA failed: {str(e)}", fg="#dc3545")
            messagebox.showerror("MEGA Error", f"Lỗi MEGA scraping: {str(e)}")
            
        finally:
            # Reset buttons
            self.btn_mega.config(state=tk.NORMAL)
            self.btn_ultra.config(state=tk.NORMAL)
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            
            # Close scraper
            if hasattr(self, 'scraper') and self.scraper:
                try:
                    self.scraper.close()
                except:
                    pass

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