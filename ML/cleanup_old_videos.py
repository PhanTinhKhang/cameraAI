#!/usr/bin/env python3
"""
Script xóa video cũ hơn 24 giờ - Windows Version

Cách chạy:
1. Chạy thủ công: python cleanup_old_videos.py
2. Tự động với Task Scheduler (xem hướng dẫn bên dưới)

HƯỚNG DẪN SETUP TASK SCHEDULER TRÊN WINDOWS:
----------------------------------------------
1. Mở Task Scheduler (tìm "Task Scheduler" trong Start Menu)
2. Click "Create Basic Task..."
3. Name: "Video Cleanup 24h"
4. Trigger: Daily hoặc Hourly
5. Action: "Start a program"
   - Program/script: C:\Python\python.exe (đường dẫn Python của bạn)
   - Arguments: cleanup_old_videos.py
   - Start in: C:\path\to\your\script\folder
6. Finish

Hoặc tạo file .bat để chạy dễ hơn (xem create_task.bat bên dưới)
"""

import os
import time
import datetime
from pathlib import Path

# =========================
# CONFIG
# =========================
CONTINUOUS_VIDEO_DIR = "../continuous_recordings"
ALERT_VIDEO_DIR = "../alerts"

# Xóa file cũ hơn 24 giờ
MAX_AGE_HOURS = 24
MAX_AGE_SECONDS = MAX_AGE_HOURS * 3600

# Có xóa alert videos không? (Thường giữ lại lâu hơn)
CLEANUP_ALERTS = False  # Set True nếu muốn xóa cả alert videos

# =========================
# CLEANUP FUNCTIONS
# =========================

def get_file_age_seconds(filepath):
    """Lấy tuổi của file tính bằng giây"""
    try:
        mtime = os.path.getmtime(filepath)
        return time.time() - mtime
    except:
        return 0

def cleanup_directory(directory, max_age_seconds, description="videos"):
    """Xóa các file cũ hơn max_age_seconds trong directory"""
    if not os.path.exists(directory):
        print(f"⚠️  Directory không tồn tại: {directory}")
        return
    
    deleted_count = 0
    deleted_size = 0
    kept_count = 0
    
    print(f"\n🔍 Scanning {description} in: {directory}")
    
    # Duyệt tất cả file .mp4 trong thư mục và sub-folders
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if not filename.endswith('.mp4'):
                continue
                
            filepath = os.path.join(root, filename)
            file_age = get_file_age_seconds(filepath)
            file_age_hours = file_age / 3600
            
            if file_age > max_age_seconds:
                try:
                    file_size = os.path.getsize(filepath)
                    os.remove(filepath)
                    deleted_count += 1
                    deleted_size += file_size
                    print(f"🗑️  Deleted: {filepath} (age: {file_age_hours:.1f}h)")
                except Exception as e:
                    print(f"❌ Error deleting {filepath}: {e}")
            else:
                kept_count += 1
    
    # Xóa các thư mục rỗng
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):  # Thư mục rỗng
                    os.rmdir(dir_path)
                    print(f"🗑️  Removed empty directory: {dir_path}")
            except:
                pass
    
    # Summary
    deleted_size_mb = deleted_size / (1024 * 1024)
    print(f"\n📊 Summary for {description}:")
    print(f"   ✅ Kept: {kept_count} files")
    print(f"   🗑️  Deleted: {deleted_count} files ({deleted_size_mb:.2f} MB)")
    
    return deleted_count, deleted_size

def main():
    print("="*60)
    print(f"🧹 Video Cleanup Started - {datetime.datetime.now()}")
    print(f"⏰ Max age: {MAX_AGE_HOURS} hours")
    print("="*60)
    
    total_deleted = 0
    total_size = 0
    
    # Cleanup continuous recordings (24/7)
    count, size = cleanup_directory(
        CONTINUOUS_VIDEO_DIR, 
        MAX_AGE_SECONDS,
        "24/7 recordings"
    )
    total_deleted += count
    total_size += size
    
    # Cleanup alert videos (nếu được enable)
    if CLEANUP_ALERTS:
        count, size = cleanup_directory(
            ALERT_VIDEO_DIR,
            MAX_AGE_SECONDS,
            "alert videos"
        )
        total_deleted += count
        total_size += size
    else:
        print(f"\nℹ️  Skipping alert videos (CLEANUP_ALERTS=False)")
    
    # Final summary
    print("\n" + "="*60)
    print(f"✅ Cleanup Complete!")
    print(f"   Total deleted: {total_deleted} files")
    print(f"   Total freed: {total_size / (1024*1024):.2f} MB")
    print(f"   Finished: {datetime.datetime.now()}")
    print("="*60)

if __name__ == "__main__":
    main()