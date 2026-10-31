import sys
import os
import subprocess
import re

mode = os.environ.get("MODE", "auto")
num_shorts = int(os.environ.get("NUM_SHORTS", "3"))
layout = os.environ.get("LAYOUT", "author")

timestamps_input = os.environ.get("TIMESTAMPS", "")
custom_duration_mins = int(os.environ.get("DURATION_MINS", "0"))
custom_duration_secs = int(os.environ.get("DURATION_SECS", "30"))
custom_duration = (custom_duration_mins * 60) + custom_duration_secs

if mode == "auto":
    print(f"🤖 AI scanning audio for peaks (Finding {num_shorts} shorts)...")
    cmd_scan = ["ffmpeg", "-i", "video.mp4", "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"]
    result = subprocess.run(cmd_scan, capture_output=True, text=True)
    log = result.stderr
    
    timestamps = []
    for line in log.split('\n'):
        if 'pts_time:' in line and 'RMS_level' in line:
            match = re.search(r"pts_time:([\d.]+)", line)
            if match: timestamps.append(float(match.group(1)))
            
    events = []
    if timestamps:
        current = [timestamps[0]]
        for i in range(1, len(timestamps)):
            if timestamps[i] - timestamps[i-1] < 5.0: current.append(timestamps[i])
            else:
                events.append(current); current = [timestamps[i]]
        events.append(current)
        
    clips_to_make = []
    for i in range(min(num_shorts, len(events))):
        peak_start = events[i][0]
        peak_end = events[i][-1]
        start_sec = max(0, peak_start - 20)
        duration = (peak_end - start_sec) + 20
        clips_to_make.append({"start": start_sec, "duration": duration})

else:
    print("📝 Manual Mode selected...")
    clips_to_make = []
    # Input format: "00:00:10, 00:05:00" (Comma separated)
    times = [t.strip() for t in timestamps_input.split(",") if t.strip()]
    for t in times:
        parts = t.split(":")
        if len(parts) == 3:
            h, m, s = parts
            start_sec = int(h)*3600 + int(m)*60 + int(s)
            clips_to_make.append({"start": start_sec, "duration": custom_duration})

for i, clip in enumerate(clips_to_make):
    start_sec = clip["start"]
    duration = clip["duration"]
    print(f"Creating Short {i+1} at {start_sec}s for {duration}s...")
    
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