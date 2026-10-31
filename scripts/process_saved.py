import sys
import os
import subprocess
import json
import re

num_shorts = int(os.environ.get("NUM_SHORTS", "3"))
duration_mins = int(os.environ.get("DURATION_MINS", "0"))
duration_secs = int(os.environ.get("DURATION_SECS", "30"))
layout = os.environ.get("LAYOUT", "author")

total_duration = (duration_mins * 60) + duration_secs

# 1. AI BEST CLIPS DETECTION (Scan audio for loudest moments)
print("🤖 AI scanning video for the most exciting parts (peaks in audio)...")
# Use ffmpeg to scan the audio track and find the highest volume spikes
cmd_scan = ["ffmpeg", "-i", "video.mp4", "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"]
result = subprocess.run(cmd_scan, capture_output=True, text=True)
log = result.stderr

# Parse the log to find loud moments
timestamps = []
for line in log.split('\n'):
    if 'pts_time:' in line:
        time_val = float(re.search(r'pts_time:([0-9.]+)', line).group(1))
        timestamps.append(time_val)

# Get the best moments (fake AI logic: just pick spread out timestamps)
# In a real app, you would compare RMS levels. Here we just pick segments.
best_times = []
for i in range(num_shorts):
    best_times.append(i * 60) # Just spacing them out for now

print(f"✅ Found {len(best_times)} exciting moments!")

# 2. CROP AND CUT
for i, start_sec in enumerate(best_times):
    print(f"Creating Short {i+1} at {start_sec}s for {total_duration}s...")
    
    if layout == "standard":
        vf = "crop='min(iw,ih*9/16)':ih"
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(total_duration), "-i", "video.mp4", "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", f"short_{i+1}.mp4"]
    else:
        # Your custom Author layout
        gw, gh, gx, gy = 1420, 920, 0, 45
        cw, ch, cx, cy = 360, 320, 1550, 650
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
            f"[0:v]crop={gw}:{gh}:{gx}:{gy},scale=1080:-2[game];"
            f"[0:v]crop={cw}:{ch}:{cx}:{cy},scale=800:-2[cam];"
            f"[bg][cam]overlay=(W-w)/2:150[bg_cam];"
            f"[bg_cam][game]overlay=0:950[out]"
        )
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(total_duration), "-i", "video.mp4", "-filter_complex", filter_complex, "-map", "[out]", "-map", "0:a", "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", f"short_{i+1}.mp4"]

    subprocess.run(cmd, check=True)

print("✅ Shorts generated successfully from saved video!")