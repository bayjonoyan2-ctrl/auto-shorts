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
    print(f"🤖 AI scanning the ENTIRE video for spikes (gunshots, shouting)...")
    cmd_scan = ["ffmpeg", "-i", "video.mp4", "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"]
    result = subprocess.run(cmd_scan, capture_output=True, text=True)
    log = result.stderr
    
    peaks = []
    current_time = 0.0
    for line in log.split('\n'):
        time_match = re.search(r"pts_time:([\d.]+)", line)
        if time_match: current_time = float(time_match.group(1))
        
        vol_match = re.search(r"RMS_level=([-\d.]+)", line)
        if vol_match and time_match:
            vol = float(vol_match.group(1))
            peaks.append((current_time, vol))
            
    # Sort by highest volume (loudest spikes at the top)
    peaks.sort(key=lambda x: x[1], reverse=True)
    
    selected_peaks = []
    for time, vol in peaks:
        if len(selected_peaks) >= num_shorts: break
        # Keep them at least 45 seconds apart so they aren't the same fight
        if all(abs(time - p[0]) > 45 for p in selected_peaks):
            selected_peaks.append((time, vol))
            
    # Sort back to chronological order (earliest first)
    selected_peaks.sort(key=lambda x: x[0])
    
    for time, vol in selected_peaks:
        # Start 10 seconds before the spike so the viewer sees the build-up
        start_sec = max(0, int(time - 10)) 
        clips_to_make.append({"start": start_sec, "duration": 45})

elif mode == "manual":
    times = [t.strip() for t in timestamps_input.split(",") if t.strip()]
    for t in times:
        parts = t.split(":")
        if len(parts) == 3:
            h, m, s = parts
            start_sec = int(h)*3600 + int(m)*60 + int(s)
            clips_to_make.append({"start": start_sec, "duration": custom_duration})

if not clips_to_make:
    print("❌ Error: No peaks found or no manual timestamps provided.")
    sys.exit(1)

for i, clip in enumerate(clips_to_make):
    start_sec = clip["start"]
    duration = clip["duration"]
    print(f"Creating Short {i+1} at {start_sec}s for {duration}s...")
    
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