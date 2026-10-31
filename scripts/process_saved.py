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

cmd_probe = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", "video.mp4"]
res_raw = subprocess.run(cmd_probe, capture_output=True, text=True).stdout.strip()
nums = [int(s) for s in re.findall(r'\d+', res_raw)]
vid_w, vid_h = nums[0], nums[1]
scale_factor = vid_w / 1920.0 

if mode == "auto":
    print(f"🤖 AI scanning...")
    duration_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", "video.mp4"]
    vid_dur = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())
    
    segment_length = vid_dur / (num_shorts + 1)
    for i in range(1, num_shorts + 1):
        start_sec = int(segment_length * i)
        clips_to_make.append({"start": start_sec, "duration": 45})

elif mode == "manual":
    print("📝 Manual Mode...")
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
    temp_vid = f"temp_vid_{i+1}.mp4"
    temp_aud = f"temp_aud_{i+1}.aac"
    
    print(f"Creating Short {i+1} at {start_sec}s for {duration}s...")
    
    # STEP 1: Extract Video ONLY (no audio) to temp file
    cmd_vid = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), "-i", "video.mp4", "-an", "-c:v", "copy", temp_vid]
    subprocess.run(cmd_vid, check=True)

    # STEP 2: Extract Audio ONLY to separate file. This fixes desync.
    cmd_aud = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), "-i", "video.mp4", "-vn", "-c:a", "aac", temp_aud]
    subprocess.run(cmd_aud, check=True)

    # STEP 3: Combine them back together into the vertical layout
    if layout == "standard":
        vf = "crop='min(iw,ih*9/16)':ih"
        cmd_final = ["ffmpeg", "-y", "-i", temp_vid, "-i", temp_aud, "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", f"short_{i+1}.mp4"]
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
            f"[0:v]split=3[bg_in][game_in][cam_in];"
            f"[bg_in]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
            f"[game_in]crop={gw}:{gh}:{gx}:{gy},scale=1080:-2[game];"
            f"[cam_in]crop={cw}:{ch}:{cx}:{cy},scale=800:-2[cam];"
            f"[bg][cam]overlay=(W-w)/2:50[bg_cam];"
            f"[bg_cam][game]overlay=0:700[out]"
        )
        
        cmd_final = [
            "ffmpeg", "-y", "-i", temp_vid, "-i", temp_aud, 
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", 
            "-c:a", "aac", "-b:a", "192k", 
            f"short_{i+1}.mp4"
        ]

    subprocess.run(cmd_final, check=True)
    
    # Cleanup
    if os.path.exists(temp_vid): os.remove(temp_vid)
    if os.path.exists(temp_aud): os.remove(temp_aud)

print("✅ All Shorts generated successfully!")