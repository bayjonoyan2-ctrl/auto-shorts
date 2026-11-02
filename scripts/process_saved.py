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
from llama_cpp import Llama
from huggingface_hub import hf_hub_download

mode = os.environ.get("MODE", "auto")
num_shorts = int(os.environ.get("NUM_SHORTS", "3"))

clips_to_make = []

# 1. YAMNet Hype Detection
if mode == "auto":
    print("🎬 Extracting audio...")
    subprocess.run(["ffmpeg", "-y", "-i", "video.mp4", "-vn", "-ac", "1", "-ar", "16000", "audio.wav"], check=True)
    
    print("🧠 Loading YAMNet...")
    model = hub.load("https://tfhub.dev/google/yamnet/1")
    with open(model.class_map_path().numpy().decode()) as f:
        names = [r["display_name"] for r in csv.DictReader(f)]
    def ids(keys): return [names.index(k) for k in keys if k in names]
    VOICE = ids(["Shout", "Yell", "Screaming", "Laughter"])
    ACTION = ids(["Gunshot", "Explosion"])
    
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
    
    # 2. Transcription & Subtitles
    print("🔍 Transcribing clips for subtitles and titles...")
    sv = AutoModel(model="iic/SenseVoiceSmall", device="cpu", disable_update=True)
    for i, t in enumerate(candidates):
        start_sec = max(0, t - 10)
        clip_wav = f"cand_{i}.wav"
        subprocess.run(["ffmpeg", "-y", "-ss", str(start_sec), "-t", "45", "-i", "audio.wav", clip_wav], check=True, capture_output=True)
        raw = sv.generate(input=clip_wav, language="zh", use_itn=True)[0]["text"]
        text = rich_transcription_postprocess(raw)
        clips_to_make.append({"start": int(start_sec), "duration": 45, "text": text})

    # 3. Generate English Titles using Qwen 1.5B
    print("🧠 Generating English Titles (Qwen 1.5B)...")
    path = hf_hub_download("Qwen/Qwen2.5-1.5B-Instruct-GGUF", "qwen2.5-1.5b-instruct-q4_k_m.gguf")
    llm = Llama(model_path=path, n_ctx=2048, n_threads=4, verbose=False)
    
    for i, clip in enumerate(clips_to_make):
        prompt = f"Translate this Chinese gaming text into a short, clickbait English YouTube Shorts title (max 50 characters):\n{clip['text'][:100]}"
        out = llm.create_chat_completion(messages=[{"role": "user", "content": prompt}], max_tokens=20, temperature=0.7)
        clip["title"] = out["choices"][0]["message"]["content"].strip()
        
        # Create .srt subtitle file
        with open(f"short_{i+1}.srt", "w", encoding="utf-8") as f:
            f.write(f"1\n00:00:00,000 --> 00:00:{clip['duration']},000\n{clip['title']}\n")

# 4. Render Video
for i, clip in enumerate(clips_to_make):
    start_sec = clip["start"]
    duration = clip["duration"]
    print(f"Creating Short {i+1}: {clip['title']}...")
    
    GAME_W, GAME_H, GAME_X, GAME_Y = 1420, 920, 0, 45
    CAM_W, CAM_H, CAM_X, CAM_Y = 360, 320, 1550, 650
    
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5,eq=brightness=-0.2:saturation=1.2[bg];"
        f"[0:v]crop={GAME_W}:{GAME_H}:{GAME_X}:{GAME_Y},scale=1080:-2[game];"
        f"[0:v]crop={CAM_W}:{CAM_H}:{CAM_X}:{CAM_Y},scale=800:-2[cam];"
        f"[bg][cam]overlay=(W-w)/2:150[bg_cam];"
        f"[bg_cam][game]overlay=0:950[out]"
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

print("✅ All Shorts, Titles, and Subtitles generated successfully!")