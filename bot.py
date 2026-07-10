import asyncio
import os
import random
import subprocess
import json
import time
from pyrogram import Client, filters

# --- User Credentials ---
API_ID = 34256648
API_HASH = "0745651c919deb785fea32bf664cd262"
BOT_TOKEN = "8957273983:AAGX8DWHBQ7CL4xzu6kwMEAfywawzZh2XRY"

app = Client("SupremeBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Progress Bar Helpers ---
def progress_bar(current, total):
    percent = (current / total) * 100
    return f"[{'█' * int(percent // 10)}{'░' * (10 - int(percent // 10))}] {percent:.1f}%"

async def progress_callback(current, total, msg, action):
    if total == 0: return
    if current % (1024 * 1024 * 5) == 0 or current == total:  
        try:
            await msg.edit_text(f"⏳ **{action}...**\n{progress_bar(current, total)}")
        except:
            pass

# --- Video Info Probe ---
async def get_video_info(video_path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, _ = await proc.communicate()
    data = json.loads(stdout)
    info = {"width": 0, "height": 0, "fps": 30.0, "has_audio": False, "duration": 0.0}
    for stream in data.get("streams", []):
        if stream["codec_type"] == "video":
            info["width"], info["height"] = int(stream.get("width", 0)), int(stream.get("height", 0))
            fps_str = stream.get("r_frame_rate", "30/1")
            num, den = map(float, fps_str.split("/"))
            info["fps"] = num / den if den != 0 else 30.0
        elif stream["codec_type"] == "audio":
            info["has_audio"] = True
    info["duration"] = float(data.get("format", {}).get("duration", 0))
    return info

# --- HACKER AI: EXTREME SUPREME TRANSFORM ENGINE ---
async def supreme_transform_video(input_path, output_path, msg):
    await msg.edit_text("🔍 **Initializing Hacker AI Supreme Mode...**\nInjecting randomized obfuscation parameters.")
    info = await get_video_info(input_path)
    W, H = info["width"], info["height"]
    
    if W == 0 or H == 0:
        return False

    # 1. RANDOMIZE EVERYTHING (Fingerprint destruction)
    rng = random.Random()
    zoom = round(rng.uniform(1.05, 1.12), 3)
    bri = round(rng.uniform(0.03, 0.08), 3)
    con = round(rng.uniform(0.01, 0.05), 3)
    sat = round(rng.uniform(-0.08, -0.02), 3)
    spd = round(rng.uniform(1.02, 1.08), 3)
    pitch = round(rng.uniform(-2.5, -0.5), 2)
    tgt_fps = rng.choice([23.976, 24, 25, 29.97, 30])
    gop_size = rng.randint(12, 250)
    pitch_factor = round(2 ** (pitch / 12.0), 6)

    # Color Channel Mixer Randomization (RGB Cross-mix)
    rg = round(rng.uniform(-0.02, 0.02), 3)
    rb = round(rng.uniform(-0.02, 0.02), 3)
    gr = round(rng.uniform(-0.02, 0.02), 3)
    gb = round(rng.uniform(-0.02, 0.02), 3)
    br = round(rng.uniform(-0.02, 0.02), 3)
    bg = round(rng.uniform(-0.02, 0.02), 3)

    # Chroma offset randomization
    offset_x = rng.randint(0, 4)
    offset_y = rng.randint(0, 4)

    # 2. BUILD VIDEO FILTER GRAPH (vf)
    zoom_w, zoom_h = int(W * zoom), int(H * zoom)
    crop_x = (zoom_w - W) // 2 + offset_x
    crop_y = (zoom_h - H) // 2 + offset_y

    vf = f"scale={zoom_w}:{zoom_h}:flags=lanczos,crop={W}:{H}:{crop_x}:{crop_y}"
    vf += f",eq=brightness={bri}:contrast={con}:saturation={sat}"
    vf += f",colorchannelmixer=rr=1:rg={rg}:rb={rb}:gr={gr}:gg=1:gb={gb}:br={br}:bg={bg}:bb=1"
    
    if rng.choice([True, False]):
        vf += ",hflip"

    vf += f",noise=c0s={rng.randint(6, 15)}:c0f=t+u,noise=alls=3:allf=t+u"
    vf += ",crop=iw-2:ih:1:0,pad=iw+2:ih:0:0"  # Chroma micro-shift
    vf += f",setpts={1/spd}*PTS,fps=fps={tgt_fps}:round=up"
    vf += ",drawtext=text='%{n}':fontsize=1:fontcolor=#010101@0.5:x=0:y=0:box=0:enable=gte(t\\,0)"

    # 3. FFMPEG COMMAND CONSTRUCTION
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-map_metadata", "-1", "-map_metadata:g", "-1",
        "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
        "-metadata", "title=", "-metadata", "creation_time=0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
        "-x264-params", f"cabac=1:ref=5:keyint={gop_size}:min-keyint={max(1, gop_size//2)}:no-deblock=1",
        "-vf", vf
    ]
    
    # Advanced Audio Filtering (Rubberband Pitch shift + Crisp Formant)
    if info["has_audio"]:
        af = f"bandpass=f=200:width_type=h:w=2000,bandpass=f=1000:width_type=h:w=3000,volume=1.2,"
        af += f"rubberband=pitch={pitch_factor}:transients=crisp:formant=preserved:channels=apart"
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-af", af]
    else:
        cmd += ["-an"]

    cmd += ["-dn", "-sn", output_path]

    await msg.edit_text("🎬 **Supreme Rendering Started (FFmpeg)...**\nExecuting multi-layer obfuscation pipeline.")
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return os.path.exists(output_path)

# --- Bot Message Handler ---
@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.video or (message.document and "video" in message.document.mime_type):
        status_msg = await message.reply_text("📥 **Starting Download...**")
        input_path = f"input_{message.id}.mp4"
        output_path = f"output_{message.id}.mp4"

        try:
            await client.download_media(message, file_name=input_path, progress=progress_callback, progress_args=(status_msg, "Downloading"))
            
            success = await supreme_transform_video(input_path, output_path, status_msg)
            
            if success:
                await status_msg.edit_text("📤 **Uploading Transformed Video...**")
                await client.send_video(
                    chat_id=message.chat.id,
                    video=output_path,
                    caption="✅ **Supreme Transform Complete**\n🔐 Video Fingerprint Destroyed\n🛠 Engine: Hacker AI v2.0",
                    progress=progress_callback,
                    progress_args=(status_msg, "Uploading")
                )
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ **Processing Failed.**")
                
        except Exception as e:
            await status_msg.edit_text(f"❌ **Error:** {str(e)}")
        finally:
            if os.path.exists(input_path): os.remove(input_path)
            if os.path.exists(output_path): os.remove(output_path)

print("🚀 Supreme Bot is Running...")
app.run()
    
