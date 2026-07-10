import asyncio
import os
import random
import glob
import subprocess
import json
import time
from pyrogram import Client, filters

# --- User Credentials ---
API_ID = 34256648
API_HASH = "0745651c919deb785fea32bf664cd262"
BOT_TOKEN = "8957273983:AAGX8DWHBQ7CL4xzu6kwMEAfywawzZh2XRY"

app = Client("SupremeBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
ffmpeg_semaphore = asyncio.Semaphore(1)

# BGM Directory Setup
BGM_DIR = "bgm_library"
os.makedirs(BGM_DIR, exist_ok=True)

def pick_random_bgm():
    bgm_files = []
    for ext in ("*.mp3", "*.wav", "*.m4a"):
        bgm_files.extend(glob.glob(os.path.join(BGM_DIR, ext)))
    return random.choice(bgm_files) if bgm_files else None

# --- Progress Bar ---
def progress_bar(percent, width=12):
    filled = int(percent / 100 * width)
    return "█" * filled + "░" * (width - filled)

async def progress_callback(current, total, msg, action, start_time):
    if total == 0: return
    elapsed = time.time() - start_time
    if elapsed < 1.5 and current != total: return  
    percent = (current / total) * 100
    try:
        await msg.edit_text(f"⏳ **{action}...**\n{progress_bar(percent)} `{percent:.1f}%`")
    except:
        pass

# --- Video Info Probe ---
async def get_video_info(video_path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, _ = await proc.communicate()
    data = json.loads(stdout)
    info = {"width": 0, "height": 0, "fps": 30.0, "has_audio": False}
    for stream in data.get("streams", []):
        if stream["codec_type"] == "video":
            info["width"], info["height"] = int(stream.get("width", 0)), int(stream.get("height", 0))
            fps_str = stream.get("r_frame_rate", "30/1")
            num, den = map(float, fps_str.split("/"))
            info["fps"] = num / den if den != 0 else 30.0
        elif stream["codec_type"] == "audio":
            info["has_audio"] = True
    return info

# --- HACKER AI: PREMIUM SUPREME TRANSFORM ENGINE v2.0 (FULL VERSION) ---
async def supreme_transform_video(input_path, output_path, new_bgm_path, msg):
    await msg.edit_text("🔍 **Analyzing Video & Injecting Obfuscation Parameters...**")
    info = await get_video_info(input_path)
    W, H = info["width"], info["height"]
    
    if W == 0 or H == 0:
        return False

    rng = random.Random()
    rng.seed(int.from_bytes(os.urandom(8), "big"))

    zoom = round(rng.uniform(1.05, 1.12), 3)
    bri, con, sat = round(rng.uniform(0.03, 0.08), 3), round(rng.uniform(0.01, 0.05), 3), round(rng.uniform(-0.08, -0.02), 3)
    spd = round(rng.uniform(1.02, 1.08), 3)
    pitch = round(rng.uniform(-2.5, -0.5), 2)
    tgt_fps = rng.choice([23.976, 24, 25, 29.97, 30])
    gop_size = rng.randint(12, 250)
    bgm_vol = round(rng.uniform(0.06, 0.12), 3)
    pitch_factor = round(2 ** (pitch / 12.0), 6)

    # Visual Filter (LUT Randomization + Noise + Shift)
    zoom_w, zoom_h = int(W * zoom), int(H * zoom)
    crop_x, crop_y = (zoom_w - W) // 2 + rng.randint(0, 4), (zoom_h - H) // 2 + rng.randint(0, 4)

    vf = f"scale={zoom_w}:{zoom_h}:flags=lanczos,crop={W}:{H}:{crop_x}:{crop_y}"
    vf += f",eq=brightness={bri}:contrast={con}:saturation={sat}"
    
    # Colorchannelmixer
    rg, rb, gr, gb, br, bg = [round(rng.uniform(-0.02, 0.02), 3) for _ in range(6)]
    vf += f",colorchannelmixer=rr=1:rg={rg}:rb={rb}:gr={gr}:gg=1:gb={gb}:br={br}:bg={bg}:bb=1"
    
    if rng.choice([True, False]): vf += ",hflip"
    vf += f",noise=c0s={rng.randint(6, 15)}:c0f=t+u,noise=alls=3:allf=t+u,crop=iw-2:ih:1:0,pad=iw+2:ih:0:0"
    vf += f",setpts={1/spd}*PTS,fps=fps={tgt_fps}:round=up"
    vf += ",drawtext=text='%{n}':fontsize=1:fontcolor=#010101@0.5:x=0:y=0:box=0:enable=gte(t\\,0)"
    
    vf_label = f"[0:v]{vf}[v]"

    # Audio Filter (Vocal Isolation + Ducking + BGM Mix)
    af_parts = []
    has_bgm = new_bgm_path and os.path.exists(new_bgm_path)

    if info["has_audio"] and has_bgm:
        af_parts.append("[0:a]asplit=2[orig_a][orig_b]")
        af_parts.append(f"[orig_a]bandpass=f=200:width_type=h:w=2000,bandpass=f=1000:width_type=h:w=3000,volume=1.2,rubberband=pitch={pitch_factor}:transients=crisp:formant=preserved:channels=apart[vocals]")
        af_parts.append(f"[orig_b][vocals]sidechaincompress=threshold=0.01:ratio=15:attack=2:release=200:makeup=1.0[ducked_bg]")
        af_parts.append(f"[ducked_bg][vocals]amix=inputs=2:duration=first:weights=1 1.5[original_audio]")
        af_parts.append(f"[1:a]volume={bgm_vol}[bgm]")
        af_parts.append(f"[original_audio][bgm]amix=inputs=2:duration=first:weights=1 0.3[a]")
    elif info["has_audio"]:
        af_parts.append(f"[0:a]rubberband=pitch={pitch_factor}:transients=crisp:formant=preserved:channels=apart[a]")

    cmd = ["ffmpeg", "-y", "-i", input_path]
    if has_bgm: cmd += ["-i", new_bgm_path]

    # Extreme Metadata Poisoning
    cmd += ["-map_metadata", "-1", "-map_metadata:g", "-1", "-map_metadata:s:v", "-1", "-map_metadata:s:a", "-1"]
    cmd += ["-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact"]
    cmd += ["-metadata", "title=", "-metadata", "creation_time=0", "-metadata", "encoder=FFmpeg"]

    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p"]
    cmd += ["-x264-params", f"cabac=1:ref=5:deblock=1:analyse=all:me=umh:subme=8:keyint={gop_size}:min-keyint={max(1, gop_size//2)}:no-deblock=1"]

    if info["has_audio"] or has_bgm:
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
    else:
        cmd += ["-an"]

    filter_complex = vf_label
    if af_parts: filter_complex += "; " + "; ".join(af_parts)
    
    cmd += ["-filter_complex", filter_complex, "-map", "[v]"]
    if af_parts: cmd += ["-map", "[a]"]
    cmd += ["-dn", "-sn", output_path]

    await msg.edit_text("🎬 **Supreme Engine Running (FFmpeg)...**\nApplying multi-layer obfuscation & audio ducking.")
    
    async with ffmpeg_semaphore:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        await process.wait()
    
    return os.path.exists(output_path)

# --- Bot Message Handler ---
@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.video or (message.document and "video" in message.document.mime_type):
        status_msg = await message.reply_text("📥 **Starting Download...**")
        input_path = f"input_{message.id}.mp4"
        output_path = f"output_{message.id}.mp4"
        bgm_path = pick_random_bgm()
        start_time = time.time()

        try:
            await client.download_media(message, file_name=input_path, progress=progress_callback, progress_args=(status_msg, "Downloading", start_time))
            
            success = await supreme_transform_video(input_path, output_path, bgm_path, status_msg)
            
            if success:
                await status_msg.edit_text("📤 **Uploading Transformed Video...**")
                upload_start = time.time()
                await client.send_video(
                    chat_id=message.chat.id,
                    video=output_path,
                    caption=f"✅ **Supreme Transform Complete**\n🔐 Video & Audio Fingerprint Destroyed.\n🎵 Auto BGM: {'Yes' if bgm_path else 'No'}",
                    progress=progress_callback,
                    progress_args=(status_msg, "Uploading", upload_start)
                )
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ **Processing Failed.** FFmpeg encountered an error.")
                
        except Exception as e:
            await status_msg.edit_text(f"❌ **Error:** `{str(e)[:200]}`")
        finally:
            if os.path.exists(input_path): os.remove(input_path)
            if os.path.exists(output_path): os.remove(output_path)

print("🚀 Supreme Bot v2.0 is Running with FULL Audio Ducking & BGM Injection...")
app.run()
    
