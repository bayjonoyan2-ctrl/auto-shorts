import sys
import os
import subprocess
import re
import json

# --- NEW AI IMPORTS ---
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("Installing faster-whisper...")
    subprocess.run([sys.executable, "-m", "pip", "install", "faster-whisper"], check=True)
    from faster_whisper import WhisperModel

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
    print("🤖 Extracting audio for AI transcription...")
    subprocess.run(["ffmpeg", "-y", "-i", "video.mp4", "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "audio.wav"], check=True)
    
    print("🤖 Loading Whisper AI Model (small)...")
    # Using 'small' model for speed on GitHub servers
    model = WhisperModel("small", device="cpu", compute_type="int8")
    
    print("🤖 Transcribing speech to find hype moments...")
    segments, info = model.transcribe("audio.wav", beam_size=5)
    
    # Keywords that indicate hype/action
    hype_keywords = ["oh", "nice", "what", "crazy", "let's go", "no way", "damn", "shit", "fuck", "wow", "holy", "bro", "look", "kill", "win", "lose", "clutch", "insane"]
    
    candidate_moments = []
    
    for segment in segments:
        text = segment.text.lower()
        # Check if any hype keyword is in the segment
        if any(keyword in text for keyword in hype_keywords):
            # Add the start time and the text for the title
            candidate_moments.append({
                "start": segment.start,
                "text": segment.text.strip(),
                "score": len([k for k in hype_keywords if k in text]) # Score based on how many keywords
            })
    
    # Sort by score (most hype words) and then by time to get spread out clips
    candidate_moments.sort(key=lambda x: x["score"], reverse=True)
    
    selected_events = []
    for moment in candidate_moments:
        if len(selected_events) >= num_shorts: break
        # Ensure clips are at least 60 seconds apart
        if all(abs(moment["start"] - ev["start"]) > 60 for ev in selected_events):
            selected_events.append(moment)
            
    # Sort chronologically
    selected_events.sort(key=lambda x: x["start"])
    
    for ev in selected_events:
        start_sec = max(0, int(ev["start"] - 5)) # Start 5s before the hype speech
        clips_to_make.append({
            "start": start_sec, 
            "duration": 60,
            "title": ev["text"][:50] # Use first 50 chars of speech as title
        })
    
    if os.path.exists("audio.wav"):
        os.remove("audio.wav")

elif mode == "manual":
    times = [t.strip() for t in timestamps_input.split(",") if t.strip()]
    for t in times:
        parts = t.split(":")
        if len(parts) == 3:
            h, m, s = parts
            start_sec = int(h)*3600 + int(m)*60 + int(s)
            clips_to_make.append({"start": start_sec, "duration": custom_duration, "title": "Manual Clip"})

if not clips_to_make:
    print("❌ Error: No hype moments found. Try lowering the AI threshold or use Manual mode.")
    sys.exit(1)

for i, clip in enumerate(clips_to_make):
    start_sec = clip["start"]
    duration = clip["duration"]
    print(f"Creating Short {i+1} at {start_sec}s with title: {clip['title']}")
    
    # (The layout code remains the same as your last working version)
    if layout == "standard":
        vf = "crop='min(iw,ih*9/16)':ih,scale=720:1280"
        cmd = ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), "-i", "video.mp4", "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-c:a", "aac", f"short_{i+1}.mp4"]
    else:
        GAME_W = int(1420 * scale_factor)
        GAME_H = int(920 * scale_factor)
        GAME_X = int(0 * scale_factor)
        GAME_Y = int(45 * scale_factor)
        CAM_W = int(360 * scale_factor)
        CAM_H = int(320 * scale_factor)
        CAM_X = int(1550 * scale_factor)
        CAM_Y = int(650 * scale_factor)

        filter_complex = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5,eq=brightness=-0.2:saturation=1.2[bg];"
            f"[0:v]crop={GAME_W}:{GAME_H}:{GAME_X}:{GAME_Y},scale=1080:-2[game];"
            f"[0:v]crop={CAM_W}:{CAM_H}:{CAM_X}:{CAM_Y},scale=800:-2[cam];"
            f"color=c=black@0.5:s=800x1000:d=1[shadow_cam];"
            f"[bg][shadow_cam]overlay=(W-w)/2+15:165[bg_shadow1];"
            f"[bg_shadow1][cam]overlay=(W-w)/2:150[bg_cam];"
            f"color=c=black@0.5:s=1080x1000:d=1[shadow_game];"
            f"[bg_cam][shadow_game]overlay=15:965[bg_shadow2];"
            f"[bg_shadow2][game]overlay=0:950[out]"
        )
        
        cmd = [
            "ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), 
            "-i", "video.mp4", 
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", 
            "-c:a", "aac", "-b:a", "128k", 
            f"short_{i+1}.mp4"
        ]

    subprocess.run(cmd, check=True)
    
    # Save title to a text file next to the video
    with open(f"short_{i+1}_title.txt", "w") as f:
        f.write(clip['title'])

print("✅ All Shorts generated successfully with AI titles!")