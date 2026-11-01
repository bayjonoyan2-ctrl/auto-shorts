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

if mode == "auto":
    print("🤖 Scanning audio...")
    cmd_audio = ["ffmpeg", "-i", "video.mp4", "-vn", "-acodec", "pcm_s16le", "-ar", "8000", "-ac", "1", "-f", "s16le", "-"]
    raw_audio = subprocess.run(cmd_audio, capture_output=True).stdout
    
    chunk_size = 16000
    max_frames = []
    for i in range(0, len(raw_audio), chunk_size):
        chunk = raw_audio[i:i+chunk_size]
        if len(chunk) < chunk_size: break
        try: max_frames.append((i // chunk_size, audioop.max(chunk, 2)))
        except: pass
            
    max_frames.sort(key=lambda x: x[1], reverse=True)
    selected = []
    for time, vol in max_frames:
        if len(selected) >= num_shorts: break
        if all(abs(time - ev[0]) > 60 for ev in selected):
            selected.append((time, vol))
    selected.sort(key=lambda x: x[0])
    
    for time, vol in selected:
        clips_to_make.append({"start": max(0, int(time - 10)), "duration": 60})

elif mode == "manual":
    times = [t.strip() for t in timestamps_input.split(",") if t.strip()]
    for t in times:
        parts = t.split(":")
        if len(parts) == 3:
            start_sec = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
            clips_to_make.append({"start": start_sec, "duration": custom_duration})

if not clips_to_make: sys.exit(1)

for i, clip in enumerate(clips_to_make):
    start_sec = clip["start"]
    duration = clip["duration"]
    print(f"Creating Short {i+1}...")
    
    if layout == "standard":
        vf = "crop='min(iw,ih*9/16)':ih,scale=720:1280"
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), "-i", "video.mp4", "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-c:a", "aac", f"short_{i+1}.mp4"]
    else:
        # 720x1280 Lite Layout - NO COLOR FILTERS, pure speed
        filter_complex = (
            f"[0:v]split=2[g][c];"
            f"[g]crop=iw*0.7:ih*0.7:0:0,scale=720:720[game];"
            f"[c]crop=iw*0.3:ih*0.3:iw*0.7:ih*0.7,scale=720:560[cam];"
            f"[game][cam]vstack[out]"
        )
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), "-i", "video.mp4", "-filter_complex", filter_complex, "-map", "[out]", "-map", "0:a", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-c:a", "aac", f"short_{i+1}.mp4"]

    subprocess.run(cmd, check=True)

print("✅ Done!")