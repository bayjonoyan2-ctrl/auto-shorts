import sys
import os
import subprocess
import re
import csv
import numpy as np
import soundfile as sf
import tensorflow_hub as hub
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess

mode = os.environ.get("MODE", "auto")
num_shorts = int(os.environ.get("NUM_SHORTS", "3"))
layout = os.environ.get("LAYOUT", "author")

cmd_probe = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", "video.mp4"]
res_raw = subprocess.run(cmd_probe, capture_output=True, text=True).stdout.strip()
nums = [int(s) for s in re.findall(r'\d+', res_raw)]
vid_w, vid_h = nums[0], nums[1]
scale_factor = vid_w / 1920.0 

clips_to_make = []

if mode == "auto":
    print("🎬 Extracting audio from VOD...")
    subprocess.run(["ffmpeg", "-y", "-i", "video.mp4", "-vn", "-ac", "1", "-ar", "16000", "audio.wav"], check=True)
    
    print("🧠 Loading YAMNet (Hype Audio Classifier)...")
    model = hub.load("https://tfhub.dev/google/yamnet/1")
    
    with open(model.class_map_path().numpy().decode()) as f:
        names = [r["display_name"] for r in csv.DictReader(f)]
        
    def ids(keys):
        return [names.index(k) for k in keys if k in names]
        
    # Detect human hype, not gunshots
    VOICE = ids(["Shout", "Yell", "Screaming", "Whoop", "Battle cry", "Laughter", "Belly laugh", "Giggle", "Chuckle, chortle"])
    ACTION = ids(["Gunshot, gunfire", "Machine gun", "Explosion"])
    
    wav, sr = sf.read("audio.wav", dtype="float32")
    HOP = 0.48 
    CHUNK = 600 * sr 
    
    voice, action = [], []
    for start in range(0, len(wav), CHUNK):
        scores, _, _ = model(wav[start:start + CHUNK])
        s = scores.numpy()
        voice.append(s[:, VOICE].max(1))
        action.append(s[:, ACTION].max(1))
        
    voice, action = np.concatenate(voice), np.concatenate(action)
    hype = voice + 0.3 * action
    hype = uniform_filter1d(hype, size=int(8 / HOP))
    
    peaks, _ = find_peaks(hype, distance=int(60 / HOP))
    top = peaks[np.argsort(hype[peaks])[::-1][:15]]
    candidates = sorted(float(p * HOP) for p in top)
    
    print(f"🔥 Found {len(candidates)} hype candidates. Verifying with AI...")
    
    sv = AutoModel(model="iic/SenseVoiceSmall", device="cpu", disable_update=True)
    HYPE_WORDS = ["卧槽", "我去", "绝了", "牛", "太强", "干掉", "击杀", "淘汰", "打爆", "残血", "吃鸡", "大吉大利", "救我", "哈哈", "不可能"]
    TAG_BONUS = {"<|LAUGHTER|>": 1.0, "<|HAPPY|>": 0.5, "<|ANGRY|>": 0.5, "<|SURPRISED|>": 0.8}
    
    results = []
    for i, t in enumerate(candidates[:num_shorts]): # Just process what we need
        start_sec = max(0, t - 20)
        clip_wav = f"cand_{i}.wav"
        subprocess.run(["ffmpeg", "-y", "-ss", str(start_sec), "-t", "45", "-i", "audio.wav", clip_wav], check=True, capture_output=True)
        
        # SenseVoice transcription
        raw = sv.generate(input=clip_wav, language="zh", use_itn=True)[0]["text"]
        text = rich_transcription_postprocess(raw)
        
        clips_to_make.append({"start": int(start_sec), "duration": 45, "title": text[:30]})
    
    if os.path.exists("audio.wav"): os.remove("audio.wav")

if not clips_to_make:
    print("❌ No clips found.")
    sys.exit(1)

for i, clip in enumerate(clips_to_make):
    start_sec = clip["start"]
    duration = clip["duration"]
    print(f"Creating Short {i+1} at {start_sec}s | Title: {clip['title']}")
    
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
    
    # Save title to a text file
    with open(f"short_{i+1}_title.txt", "w", encoding="utf-8") as f:
        f.write(clip['title'])

print("✅ All Shorts generated successfully!")