import sys
import os
import subprocess
import re

video_url = os.environ.get("VIDEO_URL")
num_shorts = int(os.environ.get("NUM_SHORTS", "3"))
zoom = os.environ.get("ZOOM", "1.0") # 1.0 is normal, 1.5 is tighter crop

if not video_url:
    print("❌ Error: VIDEO_URL is missing.")
    sys.exit(1)

print(f"⬇️ Downloading video...")
cmd_download = [
    "yt-dlp", "--cookies", "cookies.txt", "--js-runtimes", "deno",
    "--remote-components", "ejs:github", "-f", "b[ext=mp4]", 
    "-o", "input.mp4", video_url
]
subprocess.run(cmd_download, check=True)

# 1. FIND BEST PARTS (using your audio logic, simplified)
print("🤖 Scanning for loudest moments...")
# We run ffmpeg to find volume peaks and save them to a file
subprocess.run([
    "ffmpeg", "-i", "input.mp4", "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"
], stderr=open("audio_log.txt", "w"))

# In a real app, you would parse the log to find the top 3 loudest timestamps.
# For this demo, we will cut the middle of the video to show the layout works.
print("✂️ Creating Shorts with custom layout...")

# --- YOUR CUSTOM COORDINATES FROM YOUR STREAM CODE ---
GAME_W = 1420
GAME_H = 920
GAME_X = 0
GAME_Y = 45

CAM_W = 360
CAM_H = 320
CAM_X = 1550
CAM_Y = 650
# -----------------------------------------------------

for i in range(1, num_shorts + 1):
    start_sec = (i - 1) * 60 # Just skipping 60s per short for now
    
    # Calculate custom zoom width based on user input
    base_crop_width = "min(iw\\,ih*9/16)"
    zoomed_crop_width = f"({base_crop_width})/{zoom}"
    
    # FFmpeg Filter: 
    # 1. Blurred background (1080x1920)
    # 2. Crop the game using your exact X/Y/W/H
    # 3. Crop the facecam using your exact X/Y/W/H
    # 4. Overlay them on top of each other
    filter_complex = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
        f"[0:v]crop={GAME_W}:{GAME_H}:{GAME_X}:{GAME_Y},scale={zoomed_crop_width}:-2[game];"
        f"[0:v]crop={CAM_W}:{CAM_H}:{CAM_X}:{CAM_Y},scale=800:-2[cam];"
        f"[bg][cam]overlay=(W-w)/2:150[bg_cam];"
        f"[bg_cam][game]overlay=0:950[out]"
    )

    cmd = [
        "ffmpeg", "-y", "-ss", str(start_sec), "-t", "30", 
        "-i", "input.mp4",
        "-filter_complex", filter_complex,
        "-map", "[out]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", 
        f"short_{i}.mp4"
    ]
    subprocess.run(cmd, check=True)

print("✅ All Shorts created successfully!")