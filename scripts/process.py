import sys
import os
import subprocess

video_url = os.environ.get("VIDEO_URL")
num_shorts = int(os.environ.get("NUM_SHORTS", "3"))
layout = os.environ.get("LAYOUT", "custom")

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

print(f"✂️ Generating {num_shorts} Shorts using layout: {layout}...")

for i in range(1, num_shorts + 1):
    start_sec = (i - 1) * 60 
    print(f"Creating Short {i}...")
    
    if layout == "standard":
        # Standard simple crop (for regular videos)
        vf = "crop='min(iw,ih*9/16)':ih"
    elif layout == "custom":
        # YOUR CUSTOM COORDINATES FOR PUBG STREAMS
        GAME_W, GAME_H, GAME_X, GAME_Y = 1420, 920, 0, 45
        CAM_W, CAM_H, CAM_X, CAM_Y = 360, 320, 1550, 650
        
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
            f"[0:v]crop={GAME_W}:{GAME_H}:{GAME_X}:{GAME_Y},scale=1080:-2[game];"
            f"[0:v]crop={CAM_W}:{CAM_H}:{CAM_X}:{CAM_Y},scale=800:-2[cam];"
            f"[bg][cam]overlay=(W-w)/2:150[bg_cam];"
            f"[bg_cam][game]overlay=0:950[out]"
        )
        vf = None # We use filter_complex instead
    
    if layout == "standard":
        cmd = [
            "ffmpeg", "-y", "-ss", str(start_sec), "-t", "30", 
            "-i", "input.mp4", "-vf", vf, 
            "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", 
            f"short_{i}.mp4"
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-ss", str(start_sec), "-t", "30", 
            "-i", "input.mp4", "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", 
            f"short_{i}.mp4"
        ]
        
    subprocess.run(cmd, check=True)

print("✅ All Shorts created successfully!")