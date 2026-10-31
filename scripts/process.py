import sys
import os
import subprocess
import cv2
import numpy as np

video_url = os.environ.get("VIDEO_URL")
num_shorts = int(os.environ.get("NUM_SHORTS", "3"))
layout = os.environ.get("LAYOUT", "author") # author, standard, auto_detect

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

# --- AI AUTO DETECT LOGIC ---
print("🤖 Scanning video for faces (Auto-Detect)...")
cap = cv2.VideoCapture("input.mp4")
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Get a frame from the middle of the video
cap.set(cv2.CAP_PROP_POS_FRAMES, cap.get(cv2.CAP_PROP_FRAME_COUNT) // 2)
ret, frame = cap.read()
face_coords = None

if ret and layout == "auto_detect":
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    if len(faces) > 0:
        # Get the first face found
        x, y, w, h = faces[0]
        # Expand the box slightly
        face_coords = (max(0, x-50), max(0, y-50), w+100, h+100)
        print(f"✅ Face found at: {face_coords}")
    else:
        print("⚠️ No face found, falling back to Author layout.")
        layout = "author"
cap.release()

# --- LAYOUT CONFIGURATIONS ---
# Your exact coordinates from the Colab code
AUTHOR_GAME = (1420, 920, 0, 45)     # W, H, X, Y
AUTHOR_CAM = (360, 320, 1550, 650)   # W, H, X, Y

for i in range(1, num_shorts + 1):
    start_sec = (i - 1) * 60 # Skips 60 seconds per short
    print(f"Creating Short {i}...")
    
    if layout == "standard":
        vf = "crop='min(iw,ih*9/16)':ih"
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", "30", "-i", "input.mp4", "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", f"short_{i}.mp4"]
        
    elif layout == "author":
        gw, gh, gx, gy = AUTHOR_GAME
        cw, ch, cx, cy = AUTHOR_CAM
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
            f"[0:v]crop={gw}:{gh}:{gx}:{gy},scale=1080:-2[game];"
            f"[0:v]crop={cw}:{ch}:{cx}:{cy},scale=800:-2[cam];"
            f"[bg][cam]overlay=(W-w)/2:150[bg_cam];"
            f"[bg_cam][game]overlay=0:950[out]"
        )
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", "30", "-i", "input.mp4", "-filter_complex", filter_complex, "-map", "[out]", "-map", "0:a", "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", f"short_{i}.mp4"]

    elif layout == "auto_detect" and face_coords:
        fx, fy, fw, fh = face_coords
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
            f"[0:v]crop={fw}:{fh}:{fx}:{fy},scale=800:-2[cam];"
            f"[bg][cam]overlay=(W-w)/2:150[out]"
        )
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", "30", "-i", "input.mp4", "-filter_complex", filter_complex, "-map", "[out]", "-map", "0:a", "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", f"short_{i}.mp4"]

    subprocess.run(cmd, check=True)

print("✅ All Shorts created successfully!")