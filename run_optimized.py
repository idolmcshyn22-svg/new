#!/usr/bin/env python3
"""
🚀 OPTIMIZED Facebook Groups Scraper Runner
Chạy ứng dụng với các tối ưu hóa cho 1K comments
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import FB
    import tkinter as tk
    
    print("🚀 Starting MEGA OPTIMIZED Facebook Groups Scraper...")
    print("📊 All optimizations included:")
    print("   📝 Standard Mode: < 1K comments (2-5 min)")
    print("   🚀 BULK Mode: 1K-10K comments (5-15 min)")
    print("   🔥 MEGA Mode: 10K-30K comments (10-30 min)")
    print("   ⚡ 90% faster processing với virtual clicks")
    print("   💾 Streaming processing với memory management")
    print("   🎯 Enhanced UID extraction (20+ patterns)")
    print("   🧹 Clean workspace - test files removed")
    
    # Create and run GUI
    root = tk.Tk()
    app = FB.FBGroupsAppGUI(root)
    
    print("✅ GUI initialized successfully!")
    print("💡 Usage Tips:")
    print("   📝 < 1K comments: Use standard mode")
    print("   🚀 1K-10K comments: Auto BULK mode")  
    print("   🔥 10K-30K comments: Use MEGA 30K button")
    print("   🎯 Auto-detection based on limit setting")
    print("   📊 Real-time progress tracking")
    print("   💾 Streaming processing cho large volumes")
    
    root.mainloop()
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Fix: Chạy trong virtual environment:")
    print("   source venv/bin/activate")
    print("   python3 run_optimized.py")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("💡 Check console logs for details")