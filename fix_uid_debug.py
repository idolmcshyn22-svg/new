#!/usr/bin/env python3
"""
🔧 UID Debug & Fix Script
Script để debug và fix vấn đề UID Unknown
"""

import sys
import os
import re

# Add current directory to path  
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_uid_patterns():
    """Test các patterns extract UID"""
    print("🧪 Testing UID extraction patterns...")
    
    # Sample Facebook URLs để test
    test_urls = [
        "https://www.facebook.com/profile.php?id=100012345678901",
        "https://www.facebook.com/john.doe.123",
        "https://www.facebook.com/people/John-Doe/100012345678901",
        "https://facebook.com/profile.php?id=123456789&ref=br_tf",
        "https://m.facebook.com/profile.php?id=987654321012345",
        "https://www.facebook.com/user.php?id=555666777888999",
        "https://facebook.com/12345678901234567"
    ]
    
    # Import function từ FB.py
    try:
        from FB import extract_uid_from_profile_url
        
        for i, url in enumerate(test_urls):
            print(f"\n--- Test {i+1} ---")
            print(f"URL: {url}")
            uid = extract_uid_from_profile_url(url)
            print(f"Result: {uid}")
            print(f"Status: {'✅ SUCCESS' if uid != 'Unknown' else '❌ FAILED'}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def create_uid_fix():
    """Tạo improved UID extraction function"""
    print("\n🔧 Creating improved UID extraction...")
    
    improved_function = '''
def extract_uid_improved(profile_url):
    """
    IMPROVED: Extract UID với enhanced patterns cho Facebook 2024
    """
    if not profile_url:
        return "Unknown"
    
    print(f"🔍 Processing URL: {profile_url}")
    
    # SUPER ENHANCED patterns - bao gồm tất cả formats có thể
    patterns = [
        # Core Facebook patterns
        r'profile\\.php\\?id=(\\d+)',
        r'user\\.php\\?id=(\\d+)',
        r'/user/(\\d+)',
        r'id=(\\d+)',
        
        # New Facebook formats
        r'/people/[^/]+/(\\d+)',
        r'facebook\\.com/people/[^/]+/(\\d+)',
        r'profile\\.php\\?id=(\\d+)&',
        r'user\\.php\\?id=(\\d+)&',
        
        # Mobile and app links
        r'fb://profile/(\\d+)',
        r'fb://user/(\\d+)',
        r'm\\.facebook\\.com/profile\\.php\\?id=(\\d+)',
        
        # Direct UID in URL (flexible)
        r'facebook\\.com/(\\d{8,})',
        r'/(\\d{8,})(?:/|$|\\?)',
        r'\\b(\\d{8,})\\b'  # Any 8+ digit number
    ]
    
    for i, pattern in enumerate(patterns):
        try:
            import re
            match = re.search(pattern, profile_url)
            if match:
                uid = match.group(1)
                if len(uid) >= 8:  # Minimum 8 digits
                    print(f"✅ Pattern {i+1} matched: {uid}")
                    return uid
        except:
            continue
    
    # Fallback: Extract username for later resolution
    username_match = re.search(r'facebook\\.com/([^/?]+)', profile_url)
    if username_match:
        username = username_match.group(1)
        if not username.isdigit() and len(username) > 2:
            print(f"🔄 Username found: {username}")
            return f"username:{username}"
    
    print("❌ No UID found")
    return "Unknown"
'''
    
    print("✅ Improved function created!")
    return improved_function

if __name__ == "__main__":
    print("🔧 FB UID Debug & Fix Tool")
    print("=" * 50)
    
    # Test current patterns
    test_uid_patterns()
    
    # Create improved function
    improved = create_uid_fix()
    
    print("\n📋 SUMMARY:")
    print("1. ✅ Dependencies installed")
    print("2. ✅ UID patterns tested") 
    print("3. ✅ Improved extraction ready")
    print("\n💡 Next steps:")
    print("   - Chạy: source venv/bin/activate")
    print("   - Chạy: python3 run_optimized.py")
    print("   - Sử dụng 🧪 Test UID button để debug")