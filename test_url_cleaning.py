#!/usr/bin/env python3
"""
🧪 Test URL Cleaning & UID Extraction
Test cải thiện cho URLs có comment_id parameters
"""

import sys
import os
import re

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def clean_facebook_url(url):
    """Clean Facebook URL từ comment_id và các parameters không cần thiết"""
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
        
        return cleaned_url
        
    except Exception as e:
        print(f"⚠️ Error cleaning URL: {e}")
        return url

def test_url_cleaning():
    """Test URL cleaning với real URLs"""
    print("🧪 Testing URL Cleaning...")
    
    test_urls = [
        # Real URL from user's log
        "https://www.facebook.com/lan.hoang.579704?comment_id=Y29tbWVudDozMTI1ODQ4ODU3MDQ2NDUyM18zMTMyMDkxNjIwMDg4ODQyNg%3D%3D&__cft__[0]=AZVGcbfvcCftI3qb9bsOVsGJ4jlDPvL1xjZr5HpuIJk598V34E2hCW9KPymZIZsYj_oFjZ6VBQ_N91PBTGOVAjDbVOW3t-kzlTo4Zw9biBR3p9QI4A_ljJicdp3ptJPF432wSd3qk4mHiKxTS12GSR43NAdbWdigLZc-w1Ja3j6GFyiibxo5xqk2zfrPwO9yK2uHMXLjVYQi8UEjG-ucI0NLTmunHlxThL8ZNLdHRz9y4g&__tn__=R]-R",
        
        # Other test cases
        "https://www.facebook.com/john.doe.123?comment_id=test123",
        "https://facebook.com/jane.smith.456?comment_id=abc&__tn__=R",
        "https://m.facebook.com/user.name.789?comment_id=xyz&__cft__[0]=test"
    ]
    
    for i, url in enumerate(test_urls):
        print(f"\n--- Test {i+1} ---")
        print(f"Original ({len(url)} chars):")
        print(f"  {url}")
        
        cleaned = clean_facebook_url(url)
        print(f"Cleaned ({len(cleaned)} chars):")
        print(f"  {cleaned}")
        
        # Extract username
        username_match = re.search(r'facebook\.com/([^/?]+)', cleaned)
        if username_match:
            username = username_match.group(1)
            # Clean username - remove number suffix
            clean_username = re.sub(r'\.\d+$', '', username)
            print(f"Username: {username} -> Cleaned: {clean_username}")
        else:
            print("❌ No username found")

def test_uid_patterns():
    """Test UID extraction patterns"""
    print("\n🔍 Testing UID Extraction Patterns...")
    
    # Import from FB.py
    try:
        from FB import extract_uid_from_profile_url
        
        test_urls = [
            "https://www.facebook.com/lan.hoang",  # Should be username:lan.hoang
            "https://www.facebook.com/profile.php?id=123456789012345",  # Should extract UID
            "https://www.facebook.com/people/Lan-Hoang/123456789012345",  # Should extract UID
            "https://facebook.com/user.php?id=987654321012345"  # Should extract UID
        ]
        
        for i, url in enumerate(test_urls):
            print(f"\n--- UID Test {i+1} ---")
            print(f"URL: {url}")
            result = extract_uid_from_profile_url(url)
            print(f"Result: {result}")
            
            if result.startswith("username:"):
                print(f"✅ Username detected: {result.split(':', 1)[1]}")
            elif result != "Unknown":
                print(f"✅ UID extracted: {result}")
            else:
                print("❌ No UID/username found")
                
    except Exception as e:
        print(f"❌ Error testing UID patterns: {e}")

if __name__ == "__main__":
    print("🧪 URL CLEANING & UID EXTRACTION TEST")
    print("=" * 50)
    
    # Test URL cleaning
    test_url_cleaning()
    
    # Test UID patterns  
    test_uid_patterns()
    
    print("\n✅ URL CLEANING TEST COMPLETE!")
    print("\n💡 KEY IMPROVEMENTS:")
    print("  ✅ Remove comment_id parameters")
    print("  ✅ Remove __cft__ tracking parameters") 
    print("  ✅ Remove __tn__ tracking parameters")
    print("  ✅ Clean username suffixes (remove .numbers)")
    print("  ✅ Better username extraction patterns")
    
    print("\n🚀 NEXT STEPS:")
    print("1. Run: python3 run_optimized.py")
    print("2. Click 🔗 Test CommentID để test với real URLs")
    print("3. Enhanced URL cleaning sẽ improve UID resolution")
    print("4. Use 🚀 ULTRA Mode cho best performance")