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
    print(f"🤖 Running FAST native FFmpeg scanner...")
    # Using silencedetect to find loud moments natively in milliseconds
    cmd_scan = ["ffmpeg", "-i", "video.mp4", "-af", "silencedetect=noise=-30dB:d=1", "-f", "null", "-"]
    result = subprocess.run(cmd_scan, capture_output=True, text=True)
    log = result.stderr
    
    # Native FFmpeg outputs 'silence_start' and 'silence_end'. 
    # Loud moments are the gaps BETWEEN silence.
    silences = []
    for line in log.split('\n'):
        if 'silence_start:' in line:
            try: silences.append(float(line.split('silence_start:')[1].split()[0]))
            except: pass
        elif 'silence_end:' in line:
            try: silences.append(float(line.split('silence_end:')[1].split()[0]))
            except: pass
            
    # If we found silences, the loud parts are between them. 
    # If the video is constant action (no silence), we just space them out.
    if len(silences) > 2:
        # Pick gaps
        for i in range(0, len(silences)-1, 2):
            if len(clips_to_make) >= num_shorts: break
            start = int(silences[i])
            # avoid duplicates
            if not any(abs(start - c["start"]) < 60 for c in clips_to_make):
                clips_to_make.append({"start": start, "duration": 60})
                
    # Fallback if no silence found (constant gameplay)
    if not clips_to_make:
        duration_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", "video.mp4"]
        vid_dur = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())
        segment_length = vid_dur / (num_shorts + 1)
        for i in range(1, num_shorts + 1):
            clips_to_make.append({"start": int(segment_length * i), "duration": 60})

elif mode == "manual":
    times = [t.strip() for t in timestamps_input.split(",") if t.strip()]
    for t in times:
        parts = t.split(":")
        if len(parts) == 3:
            h, m, s = parts
            start_sec = int(h)*3600 + int(m)*60 + int(s)
            clips_to_make.append({"start": start_sec, "duration": custom_duration})

if not clips_to_make:
    print("❌ Error: No clips found.")
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
            "ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), 
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