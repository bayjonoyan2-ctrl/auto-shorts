import sys
import os
import subprocess

video_url = os.environ.get("VIDEO_URL")

if not video_url:
    print("❌ Error: VIDEO_URL is missing.")
    sys.exit(1)

print(f"⬇️ Downloading video: {video_url}")
subprocess.run(["yt-dlp", "-f", "mp4", "-o", "input.mp4", video_url], check=True)

print("✂️ Auto-generating 3 Shorts from different parts of the video...")

for i in range(1, 4):
    start_sec = (i - 1) * 45 
    print(f"Creating Short {i} starting at {start_sec}s...")
    
    # Fixed the crop formula for newer FFmpeg versions
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_sec), "-t", "30", 
        "-i", "input.mp4",
        "-vf", "crop='min(iw,ih*9/16)':ih", 
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", 
        f"short_{i}.mp4"
    ]
    subprocess.run(cmd, check=True)

print("✅ All Shorts created successfully!")