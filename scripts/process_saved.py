import sys
import os
import subprocess
import re
import audioop

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
    print("🤖 Extracting audio to RAM...")
    cmd_audio = ["ffmpeg", "-i", "video.mp4", "-vn", "-acodec", "pcm_s16le", "-ar", "8000", "-ac", "1", "-f", "s16le", "-"]
    raw_audio = subprocess.run(cmd_audio, capture_output=True).stdout
    
    print("🤖 Scanning entire audio for TOP spikes...")
    chunk_size = 16000
    max_frames = []
    
    for i in range(0, len(raw_audio), chunk_size):
        chunk = raw_audio[i:i+chunk_size]
        if len(chunk) < chunk_size: break
        try:
            max_val = audioop.max(chunk, 2)
            max_frames.append((i // chunk_size, max_val))
        except:
            pass
            
    # SORT ALL SPIKES FROM LOUDEST TO QUIETEST ACROSS THE WHOLE VIDEO
    max_frames.sort(key=lambda x: x[1], reverse=True)
    
    selected_events = []
    for time, vol in max_frames:
        if len(selected_events) >= num_shorts: break
        # Keep them apart so it doesn't pick the same exact fight twice
        if all(abs(time - ev[0]) > 60 for ev in selected_events):
            selected_events.append((time, vol))
            
    # Chronological order
    selected_events.sort(key=lambda x: x[0])
    
    for time, vol in selected_events:
        start_sec = max(0, int(time - 10))
        clips_to_make.append({"start": int(start_sec), "duration": 60})

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
    print(f"Creating Short {i+1} at {start_sec}s...")
    
    if layout == "standard":
        vf = "crop='min(iw,ih*9/16)':ih,scale=720:1280"
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), "-i", "video.mp4", "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-c:a", "aac", f"short_{i+1}.mp4"]
    else:
        # --- YOUR EXACT COLAB LAYOUT (BLUR + SHADOWS) ---
        GAME_W = int(1420 * scale_factor)
        GAME_H = int(920 * scale_factor)
        GAME_X = int(0 * scale_factor)
        GAME_Y = int(45 * scale_factor)

        CAM_W = int(360 * scale_factor)
        CAM_H = int(320 * scale_factor)
        CAM_X = int(1550 * scale_factor)
        CAM_Y = int(650 * scale_factor)

        filter_complex = (
            # 1. Blurry background
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5,eq=brightness=-0.2:saturation=1.2[bg];"
            # 2. Game layer
            f"[0:v]crop={GAME_W}:{GAME_H}:{GAME_X}:{GAME_Y},scale=1080:-2[game];"
            # 3. Cam layer
            f"[0:v]crop={CAM_W}:{CAM_H}:{CAM_X}:{CAM_Y},scale=800:-2[cam];"
            # 4. Shadow for cam + overlay
            f"color=c=black@0.5:s=800x1000:d=1[shadow_cam];"
            f"[bg][shadow_cam]overlay=(W-w)/2+15:165[bg_shadow1];"
            f"[bg_shadow1][cam]overlay=(W-w)/2:150[bg_cam];"
            # 5. Shadow for game + overlay
            f"color=c=black@0.5:s=1080x1000:d=1[shadow_game];"
            f"[bg_cam][shadow_game]overlay=15:965[bg_shadow2];"
            f"[bg_shadow2][game]overlay=0:950[out]"
        )
        
        # --- FIX FOR SPEED & QUALITY ---
        # We keep the 1080x1920 output, but use ultrafast + crf 24. 
        # This gives 1080p quality but renders instantly.
        cmd = [
            "ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), 
            "-i", "video.mp4", 
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "0:a",
            "-c:v", "libx264", 
            "-preset", "ultrafast", 
            "-crf", "24", 
            "-pix_fmt", "yuv420p", 
            "-c:a", "aac", "-b:a", "128k", 
            f"short_{i+1}.mp4"
        ]

    subprocess.run(cmd, check=True)

print("✅ All Shorts generated successfully!")