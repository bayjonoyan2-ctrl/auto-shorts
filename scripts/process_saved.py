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

clips_to_make = []

cmd_probe = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "csv=s=x:p=0", "video.mp4"]
res_raw = subprocess.run(cmd_probe, capture_output=True, text=True).stdout.strip()
nums = [int(s) for s in re.findall(r'\d+', res_raw)]
vid_w, vid_h = nums[0], nums[1]
scale_factor = vid_w / 1920.0 

fps_raw = res_raw.split("x")[-1] if "x" in res_raw else "30/1"
try:
    num, den = fps_raw.split("/")
    orig_fps = float(num) / float(den)
except:
    orig_fps = 30.0
target_fps = 30 if orig_fps <= 45 else 60

if mode == "auto":
    print(f"🤖 AI scanning for fights/spikes...")
    cmd_scan = ["ffmpeg", "-i", "video.mp4", "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"]
    result = subprocess.run(cmd_scan, capture_output=True, text=True)
    log = result.stderr
    
    # 1. Find all loud spikes
    spikes = []
    current_time = 0.0
    for line in log.split('\n'):
        time_match = re.search(r"pts_time:([\d.]+)", line)
        if time_match: current_time = float(time_match.group(1))
        vol_match = re.search(r"RMS_level=([-\d.]+)", line)
        if vol_match and time_match:
            spikes.append((current_time, float(vol_match.group(1))))
            
    # Sort by loudest to pick the best events globally
    spikes.sort(key=lambda x: x[1], reverse=True)
    
    selected_events = []
    for time, vol in spikes:
        if len(selected_events) >= num_shorts: break
        # Keep events 60 seconds apart
        if all(abs(time - ev[0]) > 60 for ev in selected_events):
            selected_events.append((time, vol))
            
    # 2. Group spikes into "fights"
    # If a spike happens within 8 seconds of another, they are part of the same fight.
    events_grouped = []
    for base_time, vol in selected_events:
        group = [base_time]
        for time, _ in spikes:
            if base_time - 8 <= time <= base_time + 45: # Look forward 45s for the fight duration
                group.append(time)
        events_grouped.append(group)

    # 3. Calculate start/end with 10s padding
    for group in events_grouped:
        start_time = min(group)
        end_time = max(group)
        
        start_sec = max(0, start_time - 10)
        duration = (end_time - start_sec) + 10
        
        # Cap at 3 minutes (180s)
        duration = min(duration, 180)
        
        clips_to_make.append({"start": start_sec, "duration": duration})

elif mode == "manual":
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
    print(f"Creating Short {i+1}: {start_sec}s to {start_sec+duration}s (Duration: {duration}s)...")
    
    if layout == "standard":
        vf = f"crop='min(iw,ih*9/16)':ih,fps={target_fps}"
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), "-i", "video.mp4", "-vf", vf, "-af", "aresample=async=1", "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", f"short_{i+1}.mp4"]
    else:
        gw = int(1420 * scale_factor)
        gh = int(920 * scale_factor)
        gx = int(0 * scale_factor)
        gy = int(45 * scale_factor)
        cw = int(360 * scale_factor)
        ch = int(320 * scale_factor)
        cx = int(1550 * scale_factor)
        cy = int(650 * scale_factor)

        filter_complex = (
            f"[0:v]split=2[game_in][cam_in];"
            f"color=c=black:s=1080x1920[bg];"
            f"[game_in]crop={gw}:{gh}:{gx}:{gy},scale=1080:-2[game];"
            f"[cam_in]crop={cw}:{ch}:{cx}:{cy},scale=800:-2[cam];"
            f"[bg][game]overlay=(W-w)/2:0[bg_game];"
            f"[bg_game][cam]overlay=(W-w)/2:1000,fps={target_fps}[out]"
        )
        cmd = [
            "ffmpeg", "-y", 
            "-ss", str(start_sec), "-t", str(duration), 
            "-i", "video.mp4", 
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "0:a",
            "-af", "aresample=async=1", 
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", 
            "-c:a", "aac", "-b:a", "192k", 
            f"short_{i+1}.mp4"
        ]

    subprocess.run(cmd, check=True)

print("✅ All Shorts generated successfully!")