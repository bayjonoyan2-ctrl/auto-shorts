import sys
import os
import subprocess
import re
import csv
import numpy as np
import soundfile as sf
import tensorflow as tf
import tensorflow_hub as hub
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks
import json

mode = os.environ.get("MODE", "auto")
num_shorts = int(os.environ.get("NUM_SHORTS", "3"))

clips_to_make = []

cmd_probe = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", "video.mp4"]
res_raw = subprocess.run(cmd_probe, capture_output=True, text=True).stdout.strip()
nums = [int(s) for s in re.findall(r'\d+', res_raw)]
vid_w = nums[0]
scale_factor = vid_w / 1920.0

if mode == "auto":
    print("🎬 Extracting audio...")
    subprocess.run(["ffmpeg", "-y", "-i", "video.mp4", "-vn", "-ac", "1", "-ar", "16000", "audio.wav"], check=True)
    
    print("🧠 Loading YAMNet...")
    model = hub.load("https://www.kaggle.com/models/google/yamnet/TensorFlow2/yamnet/1")
    
    with open(model.class_map_path().numpy().decode()) as f:
        names = [r["display_name"] for r in csv.DictReader(f)]
        
    def ids(keys): return [names.index(k) for k in keys if k in names]
    VOICE = ids(["Shout", "Yell", "Screaming", "Laughter"])
    ACTION = ids(["Gunshot, gunfire", "Explosion"])
    
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
    hype = uniform_filter1d(voice + 0.3 * action, size=int(8 / HOP))
    peaks, _ = find_peaks(hype, distance=int(60 / HOP))
    top = peaks[np.argsort(hype[peaks])[::-1][:num_shorts]]
    candidates = sorted(float(p * HOP) for p in top)
    
    for t in candidates:
        start_sec = max(0, t - 5)
        hype_end = t
        for check_t in np.arange(t, t + 30, HOP):
            idx = int(check_t / HOP)
            if idx < len(hype) and hype[idx] > 0.05:
                hype_end = check_t
        duration = (hype_end - start_sec) + 5
        duration = min(duration, 180)
        clips_to_make.append({"start": int(start_sec), "duration": int(duration)})

if not clips_to_make:
    print("❌ No clips found.")
    sys.exit(1)

with open("clips.json", "w") as f:
    json.dump(clips_to_make, f)

print("✅ Generating AI Titles and Subtitles...")

title_script = """
import json
import subprocess
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from llama_cpp import Llama
from huggingface_hub import hf_hub_download
import re

with open("clips.json") as f:
    clips = json.load(f)

sv = AutoModel(model="iic/SenseVoiceSmall", device="cpu", disable_update=True)
path = hf_hub_download("Qwen/Qwen2.5-1.5B-Instruct-GGUF", "qwen2.5-1.5b-instruct-q4_k_m.gguf")
llm = Llama(model_path=path, n_ctx=2048, n_threads=4, verbose=False)

for i, clip in enumerate(clips):
    start = clip["start"]
    duration = clip["duration"]
    clip_wav = f"cand_{i}.wav"
    subprocess.run(["ffmpeg", "-y", "-ss", str(start), "-t", str(duration), "-i", "audio.wav", clip_wav], capture_output=True)
    
    raw = sv.generate(input=clip_wav, language="zh", use_itn=True)[0]["text"]
    text = rich_transcription_postprocess(raw)
    
    # Translate to English subtitles
    sub_prompt = f"Translate this Chinese gaming audio into an English subtitle. Output ONLY the translation:\\n{text[:200]}"
    sub_out = llm.create_chat_completion(messages=[{"role": "user", "content": sub_prompt}], max_tokens=50, temperature=0.3)
    english_sub = sub_out["choices"][0]["message"]["content"].strip().replace('"', '')
    
    with open(f"sub_{i+1}.srt", "w", encoding="utf-8") as f:
        f.write(f"1\\n00:00:00,000 --> 00:00:{duration},000\\n{english_sub}\\n")
        
    # Create title
    prompt = f"Translate this Chinese gaming text into a short, clickbait English YouTube Shorts title (max 40 chars). Do not use quotes or punctuation:\\n{text[:100]}"
    out = llm.create_chat_completion(messages=[{"role": "user", "content": prompt}], max_tokens=20, temperature=0.8)
    title = out["choices"][0]["message"]["content"].strip()
    title = re.sub(r'[\\\\/*?:"<>|]', "", title).replace(" ", "_")
    
    with open(f"title_{i+1}.txt", "w", encoding="utf-8") as f:
        f.write(title)
"""
with open("title_gen.py", "w") as f:
    f.write(title_script)
    
subprocess.run(["python", "title_gen.py"], check=True)

print("✅ Rendering Shorts...")

for i, clip in enumerate(clips_to_make):
    start_sec = clip["start"]
    duration = clip["duration"]
    
    with open(f"title_{i+1}.txt", "r", encoding="utf-8") as f:
        video_title = f.read().strip()
        
    print(f"Creating Short: {video_title}...")
    
    GAME_W = int(1420 * scale_factor)
    GAME_H = int(920 * scale_factor)
    GAME_X = int(0 * scale_factor)
    GAME_Y = int(45 * scale_factor)
    CAM_W = int(360 * scale_factor)
    CAM_H = int(320 * scale_factor)
    CAM_X = int(1550 * scale_factor)
    CAM_Y = int(650 * scale_factor)
    
    # THE FIX: Burn the English SRT file perfectly into the video
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5,eq=brightness=-0.2:saturation=1.2[bg];"
        f"[0:v]crop={GAME_W}:{GAME_H}:{GAME_X}:{GAME_Y},scale=1080:-2[game];"
        f"[0:v]crop={CAM_W}:{CAM_H}:{CAM_X}:{CAM_Y},scale=800:-2[cam];"
        f"[bg][cam]overlay=(W-w)/2:150[bg_cam];"
        f"[bg_cam][game]overlay=0:950[base];"
        f"[base]subtitles=sub_{i+1}.srt:force_style='FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=1,Shadow=1,MarginV=20'[out]"
    )
    
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration), 
        "-i", "video.mp4", 
        "-filter_complex", filter_complex,
        "-map", "[out]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", 
        "-c:a", "aac", "-b:a", "128k", 
        f"short_{i+1}_{video_title}.mp4"
    ]
    subprocess.run(cmd, check=True)
    
    # Clean up subtitles
    if os.path.exists(f"sub_{i+1}.srt"):
        os.remove(f"sub_{i+1}.srt")

print("✅ All Shorts generated successfully!")