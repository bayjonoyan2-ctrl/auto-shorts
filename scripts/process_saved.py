import sys
import os
import subprocess
import re

num_shorts = int(os.environ.get("NUM_SHORTS", "3"))
duration_mins = int(os.environ.get("DURATION_MINS", "0"))
duration_secs = int(os.environ.get("DURATION_SECS", "30"))
layout = os.environ.get("LAYOUT", "author")

total_duration = (duration_mins * 60) + duration_secs
if total_duration > 165:
    total_duration = 165
    print("⚠️ Duration capped at 2 minutes 45 seconds (165s) for YouTube Shorts.")

print(f"🤖 AI scanning audio for the best moments (loud peaks)... This might take a few minutes.")
cmd_scan = ["ffmpeg", "-i", "video.mp4", "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"]
peak_result = subprocess.run(cmd_scan, capture_output=True, text=True)
peak_log = peak_result.stderr

timestamps = []
for line in peak_log.split('\n'):
    if 'pts_time:' in line and 'RMS_level' in line:
        match = re.search(r"pts_time:([\d.]+)", line)
        if match:
            timestamps.append(float(match.group(1)))

best_times = []
if len(timestamps) > 3:
    step = len(timestamps) // (num_shorts + 1)
    for i in range(1, num_shorts + 1):
        best_times.append(timestamps[i * step])
else:
    for i in range(num_shorts):
        best_times.append(i * 60)

print(f"✅ AI found {len(best_times)} exciting moments!")

for i, peak_sec in enumerate(best_times):
    # Start 20 seconds before the loud moment
    start_sec = max(0, peak_sec - 20)
    
    print(f"Creating Short {i+1} at {start_sec:.2f}s for {total_duration}s (Peak was at {peak_sec:.2f}s)...")
    
    if layout == "standard":
        vf = "crop='min(iw,ih*9/16)':ih"
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(total_duration), "-i", "video.mp4", "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", f"short_{i+1}.mp4"]
    else:
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

print("✅ All Shorts generated successfully!")