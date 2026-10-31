import sys
import os
import subprocess
import re

num_shorts = int(os.environ.get("NUM_SHORTS", "3"))
layout = os.environ.get("LAYOUT", "author")

print(f"🤖 AI scanning audio for peaks...")
cmd_scan = ["ffmpeg", "-i", "video.mp4", "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"]
peak_result = subprocess.run(cmd_scan, capture_output=True, text=True)
peak_log = peak_result.stderr

timestamps = []
for line in peak_log.split('\n'):
    if 'pts_time:' in line and 'RMS_level' in line:
        match = re.search(r"pts_time:([\d.]+)", line)
        if match:
            timestamps.append(float(match.group(1)))

# Group peaks that are close together to find the "event"
events = []
if timestamps:
    current_event = [timestamps[0]]
    for i in range(1, len(timestamps)):
        if timestamps[i] - timestamps[i-1] < 5.0: # If within 5 seconds, it's the same event
            current_event.append(timestamps[i])
        else:
            events.append(current_event)
            current_event = [timestamps[i]]
    events.append(current_event)

# Pick the best events
best_events = []
if len(events) > 3:
    step = len(events) // (num_shorts + 1)
    for i in range(1, num_shorts + 1):
        best_events.append(events[i * step])
else:
    best_events = events[:num_shorts]

print(f"✅ AI found {len(best_events)} exciting events!")

for i, event in enumerate(best_events):
    peak_start = event[0]
    peak_end = event[-1]
    
    # Auto-calculate duration: 20s before + peak duration + 20s after
    start_sec = max(0, peak_start - 20)
    duration = (peak_end - start_sec) + 20
    
    # Ensure it doesn't exceed 2m 45s (165s) if you want YouTube Shorts limit
    if duration > 165: duration = 165
    
    print(f"Creating Short {i+1}: Starts at {start_sec:.2f}s, Duration: {duration:.2f}s (Peak lasted {peak_end - peak_start:.2f}s)...")
    
    if layout == "standard":
        vf = "crop='min(iw,ih*9/16)':ih"
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), "-i", "video.mp4", "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", f"short_{i+1}.mp4"]
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
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), "-i", "video.mp4", "-filter_complex", filter_complex, "-map", "[out]", "-map", "0:a", "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", f"short_{i+1}.mp4"]

    subprocess.run(cmd, check=True)

print("✅ All Shorts generated successfully!")