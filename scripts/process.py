import sys
import os
import subprocess
import json

# Read inputs from GitHub Actions environment
video_url = os.environ.get("VIDEO_URL")
start_time = os.environ.get("START_TIME", "00:00:00")
end_time = os.environ.get("END_TIME", "00:00:30")

if not video_url:
    print("❌ Error: VIDEO_URL is missing.")
    sys.exit(1)

print(f"⬇️ Downloading video: {video_url}")

# Download the video using yt-dlp
subprocess.run([
    "yt-dlp", 
    "-f", "mp4", 
    "-o", "input.mp4", 
    video_url
], check=True)

print("✂️ Cropping video to 9:16 aspect ratio...")

# Use FFmpeg to crop center to 9:16 and cut timestamp
# 9:16 center crop formula: (in_w - (in_h * 9 / 16)) / 2
cmd = [
    "ffmpeg", "-y", "-ss", start_time, "-to", end_time, 
    "-i", "input.mp4",
    "-vf", "crop=min(iw\\,ih*9/16):ih", 
    "-c:v", "libx264", "-preset", "fast",
    "-c:a", "aac", 
    "output_short.mp4"
]

subprocess.run(cmd, check=True)
print("✅ Short created successfully!")