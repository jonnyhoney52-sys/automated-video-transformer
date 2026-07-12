import asyncio
import glob
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Callable, Optional, Tuple, Dict, Any

from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.errors import FloodWait

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

BASE_DIR = Path(__file__).parent.resolve()
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "outputs"
BGM_DIR = BASE_DIR / "bgm_library"

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
MAX_DURATION_SECONDS = 7200
CONCURRENT_FFMPEG_JOBS = 2

ffmpeg_semaphore = asyncio.Semaphore(CONCURRENT_FFMPEG_JOBS)

for _d in [DOWNLOAD_DIR, OUTPUT_DIR, BGM_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(BASE_DIR / "bot.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("SupremeBot")


def _format_size(bytes_: float) -> str:
    try:
        b = float(bytes_)
    except (TypeError, ValueError):
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024.0:
            return f"{b:.2f} {unit}"
        b /= 1024.0
    return f"{b:.2f} PB"


def _format_duration(seconds: float) -> str:
    try:
        s = int(float(seconds))
    except (TypeError, ValueError):
        return "0s"
    if s < 0:
        s = 0
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _progress_bar(percent: float, width: int = 12) -> str:
    try:
        p = float(percent)
    except (TypeError, ValueError):
        p = 0.0
    if p < 0:
        p = 0.0
    if p > 100:
        p = 100.0
    filled = int(round((p / 100.0) * width))
    if filled > width:
        filled = width
    if filled < 0:
        filled = 0
    empty = width - filled
    return "█" * filled + "░" * empty


def pick_random_bgm() -> Optional[str]:
    patterns = ["*.mp3", "*.wav", "*.m4a", "*.ogg", "*.flac"]
    files = []
    for pat in patterns:
        files.extend(glob.glob(str(BGM_DIR / pat)))
    if not files:
        return None
    return random.choice(files)


async def get_video_info(video_path: str) -> Dict:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path]

    result: Dict[str, Any] = {
        "width": 0,
        "height": 0,
        "fps": 30.0,
        "has_audio": False,
        "audio_codec": "",
        "audio_sample_rate": 0,
        "audio_channels": 0,
        "video_codec": "",
        "duration": 0.0,
        "size": 0,
    }

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0 or not stdout:
            return result
        data = json.loads(stdout.decode("utf-8", errors="ignore") or "{}")
    except Exception as e:
        logger.error(f"ffprobe failed: {e}")
        return result

    fmt = data.get("format", {}) or {}
    streams = data.get("streams", []) or []

    try:
        result["duration"] = float(fmt.get("duration", 0.0) or 0.0)
    except (TypeError, ValueError):
        result["duration"] = 0.0

    try:
        result["size"] = int(fmt.get("size", 0) or 0)
    except (TypeError, ValueError):
        result["size"] = 0

    for stream in streams:
        codec_type = stream.get("codec_type", "")
        if codec_type == "video" and result["width"] == 0:
            try:
                result["width"] = int(stream.get("width", 0) or 0)
            except (TypeError, ValueError):
                result["width"] = 0
            try:
                result["height"] = int(stream.get("height", 0) or 0)
            except (TypeError, ValueError):
                result["height"] = 0
            result["video_codec"] = stream.get("codec_name", "") or ""
            fps_str = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "30/1"
            try:
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    num = float(num)
                    den = float(den)
                    result["fps"] = (num / den) if den != 0 else 30.0
                else:
                    result["fps"] = float(fps_str)
            except (TypeError, ValueError, ZeroDivisionError):
                result["fps"] = 30.0
            if not result["fps"] or result["fps"] <= 0:
                result["fps"] = 30.0
            if result["duration"] == 0.0:
                try:
                    result["duration"] = float(stream.get("duration", 0.0) or 0.0)
                except (TypeError, ValueError):
                    result["duration"] = 0.0
        elif codec_type == "audio":
            result["has_audio"] = True
            result["audio_codec"] = stream.get("codec_name", "") or ""
            try:
                result["audio_sample_rate"] = int(stream.get("sample_rate", 0) or 0)
            except (TypeError, ValueError):
                result["audio_sample_rate"] = 0
            try:
                result["audio_channels"] = int(stream.get("channels", 0) or 0)
            except (TypeError, ValueError):
                result["audio_channels"] = 0

    return result


async def supreme_transform_video(
    input_video_path: str,
    output_video_path: str,
    new_bgm_path: Optional[str] = None,
    *,
    zoom_scale: Optional[float] = None,
    brightness: Optional[float] = None,
    contrast: Optional[float] = None,
    saturation: Optional[float] = None,
    mirror: Optional[bool] = None,
    target_fps: Optional[float] = None,
    speed_factor: Optional[float] = None,
    bgm_volume: Optional[float] = None,
    pitch_semitones: Optional[float] = None,
    noise_strength: Optional[int] = None,
    chroma_shift: bool = True,
    enable_drawtext: bool = True,
    color_channel_mix: bool = True,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    task_id: str = "",
) -> bool:
    # Step 1 — PROBE
    info = await get_video_info(input_video_path)
    W = int(info.get("width", 0) or 0)
    H = int(info.get("height", 0) or 0)
    src_fps = float(info.get("fps", 30.0) or 30.0)
    has_audio = bool(info.get("has_audio", False))
    duration = float(info.get("duration", 0.0) or 0.0)

    if W <= 0:
        W = 1280
    if H <= 0:
        H = 720
    if src_fps <= 0:
        src_fps = 30.0

    # Step 2 — RANDOMIZE EVERY PARAMETER
    rng = random.Random(int.from_bytes(os.urandom(8), "big"))

    zoom = zoom_scale or round(rng.uniform(1.05, 1.12), 3)
    bri = brightness if brightness is not None else round(rng.uniform(0.03, 0.08), 3)
    con = contrast if contrast is not None else round(rng.uniform(0.01, 0.05), 3)
    sat = saturation if saturation is not None else round(rng.uniform(-0.08, -0.02), 3)
    flip = mirror if mirror is not None else rng.choice([True, False])
    spd = speed_factor or round(rng.uniform(1.02, 1.08), 3)
    pitch = pitch_semitones if pitch_semitones is not None else round(rng.uniform(-2.5, -0.5), 2)
    bgm_vol = bgm_volume if bgm_volume is not None else round(rng.uniform(0.05, 0.08), 3)
    nz = noise_strength or rng.randint(6, 15)
    gop_size = rng.randint(12, 250)
    chroma_off_x = rng.randint(0, 3)
    chroma_off_y = rng.randint(0, 3)

    rr = 1.0
    rg = round(rng.uniform(-0.03, 0.03), 4)
    rb = round(rng.uniform(-0.03, 0.03), 4)
    gr = round(rng.uniform(-0.03, 0.03), 4)
    gg = 1.0
    gb = round(rng.uniform(-0.03, 0.03), 4)
    br = round(rng.uniform(-0.03, 0.03), 4)
    bg = round(rng.uniform(-0.03, 0.03), 4)
    bb = 1.0

    pitch_factor = round(2 ** (pitch / 12.0), 6)

    std_fps_list = [23.976, 24, 25, 29.97, 30, 50, 59.94]
    if target_fps:
        tgt_fps = target_fps
    else:
        tgt_fps = min(std_fps_list, key=lambda x: abs(x - src_fps))
        if abs(tgt_fps - src_fps) < 0.5:
            alt = [f for f in std_fps_list if abs(f - src_fps) > 1]
            tgt_fps = rng.choice(alt) if alt else 29.97

    # Step 3 — BUILD VIDEO FILTER CHAIN
    zoom_w = int(W * zoom)
    zoom_h = int(H * zoom)
    crop_x = (zoom_w - W) // 2 + chroma_off_x
    crop_y = (zoom_h - H) // 2 + chroma_off_y

    vf = f"scale={zoom_w}:{zoom_h}:flags=lanczos"
    vf += f",crop={W}:{H}:{crop_x}:{crop_y}"
    vf += f",eq=brightness={bri}:contrast={con}:saturation={sat}"
    vf += f",colorchannelmixer=rr={rr}:rg={rg}:rb={rb}:gr={gr}:gg={gg}:gb={gb}:br={br}:bg={bg}:bb={bb}"

    if flip:
        vf += ",hflip"

    vf += f",noise=c0s={nz}:c0f=t+u"
    vf += ",noise=alls=3:allf=t+u"

    if chroma_shift:
        vf += f",crop=iw-{chroma_off_x+1}:ih:{chroma_off_x}:0,pad=iw+{chroma_off_x+1}:ih:0:0"

    vf += f",setpts={1/spd}*PTS"
    vf += f",fps=fps={tgt_fps:.4f}:round=up"

    if enable_drawtext:
        vf += ",drawtext=text='%{n}':fontsize=1:fontcolor=#010101@0.5:x=0:y=0:box=0:enable=gte(t\\,0)"

    vf = f"[0:v]{vf}[v]"

    # Step 4 — BUILD AUDIO FILTER CHAIN
    af_parts = []
    has_bgm = bool(new_bgm_path and os.path.exists(new_bgm_path))

    if has_audio and has_bgm:
        af_parts.append(f"[0:a][1:a]amix=inputs=2:duration=first:weights=1.0 {bgm_vol},rubberband=pitch={pitch_factor}:transients=crisp:formant=preserved:channels=apart[a]")
    elif has_audio and not has_bgm:
        af_parts.append(f"[0:a]rubberband=pitch={pitch_factor}:transients=crisp:formant=preserved:channels=apart[a]")
    elif not has_audio and has_bgm:
        af_parts.append(f"[1:a]volume={bgm_vol}[a]")

    # Step 5 — BUILD FFMPEG COMMAND
    cmd = ["ffmpeg", "-y"]
    cmd += ["-i", input_video_path]
    if has_bgm:
        cmd += ["-i", new_bgm_path]

    cmd += ["-map_metadata", "-1"]
    cmd += ["-map_metadata:g", "-1"]
    cmd += ["-map_metadata:s:v", "-1"]
    cmd += ["-map_metadata:s:a", "-1"]
    cmd += ["-fflags", "+bitexact"]
    cmd += ["-flags:v", "+bitexact"]
    cmd += ["-flags:a", "+bitexact"]

    for _tag in ["title", "comment", "description", "copyright", "creation_time", "encoder", "artist", "album", "genre", "date", "track", "disc"]:
        cmd += ["-metadata", f"{_tag}="]

    cmd += ["-c:v", "libx264"]
    cmd += ["-preset", "medium"]
    cmd += ["-crf", "23"]
    cmd += ["-pix_fmt", "yuv420p"]
    cmd += ["-x264-params", f"cabac=1:ref=5:deblock=1:analyse=all:me=umh:subme=8:keyint={gop_size}:min-keyint={max(1, gop_size//2)}:no-deblock=1"]

    if has_audio or has_bgm:
        cmd += ["-c:a", "aac"]
        cmd += ["-b:a", "128k"]
        cmd += ["-ar", "44100"]
        cmd += ["-ac", "2"]

    all_filters = [vf]
    if af_parts:
        all_filters.append("; ".join(af_parts))
    cmd += ["-filter_complex", "; ".join(all_filters)]
    cmd += ["-map", "[v]"]
    if af_parts:
        cmd += ["-map", "[a]"]
    cmd += ["-dn", "-sn"]
    cmd += [output_video_path]

    # Step 6 — EXECUTE FFMPEG
    logger.info(f"[{task_id}] FFmpeg command: {' '.join(cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except Exception as e:
        logger.error(f"[{task_id}] Failed to start ffmpeg: {e}")
        return False

    time_re = re.compile(r"time=(\d+):(\d+):(\d+\.?\d*)")
    last_reported = {"pct": 0.0}

    async def _monitor_stderr():
        while True:
            try:
                line_bytes = await process.stderr.readline()
            except Exception:
                break
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="ignore")
            m = time_re.search(line)
            if m:
                try:
                    hh = float(m.group(1))
                    mm = float(m.group(2))
                    ss = float(m.group(3))
                    current_sec = hh * 3600 + mm * 60 + ss
                except (TypeError, ValueError):
                    continue
                if duration and duration > 0:
                    percentage = 10.0 + (current_sec / duration) * 85.0
                else:
                    percentage = 10.0
                if percentage > 95.0:
                    percentage = 95.0
                if percentage - last_reported["pct"] >= 5.0:
                    last_reported["pct"] = percentage
                    if progress_callback:
                        bar = _progress_bar(percentage)
                        text = f"⚙️ Transforming...\n\n{bar} {percentage:.1f}%\n🎞 {_format_duration(current_sec)} / {_format_duration(duration)}"
                        try:
                            res = progress_callback(text, percentage)
                            if asyncio.iscoroutine(res):
                                await res
                        except Exception as ce:
                            logger.error(f"[{task_id}] progress_callback error: {ce}")

    monitor_task = asyncio.create_task(_monitor_stderr())

    try:
        await asyncio.wait_for(process.wait(), timeout=MAX_DURATION_SECONDS)
    except asyncio.TimeoutError:
        logger.error(f"[{task_id}] FFmpeg timed out.")
        try:
            process.kill()
        except Exception:
            pass
        monitor_task.cancel()
        return False

    try:
        await monitor_task
    except Exception:
        pass

    if process.returncode != 0:
        logger.error(f"[{task_id}] FFmpeg exited with code {process.returncode}")
        return False

    if not os.path.exists(output_video_path):
        logger.error(f"[{task_id}] Output file not found: {output_video_path}")
        return False

    if os.path.getsize(output_video_path) <= 0:
        logger.error(f"[{task_id}] Output file is empty: {output_video_path}")
        return False

    logger.info(f"[{task_id}] Transform successful: {output_video_path}")
    return True


async def _dl_progress(current: int, total: int, msg: Message, status_msg: Message, start: float):
    now = time.time()
    if not hasattr(_dl_progress, "_last"):
        _dl_progress._last = {}
    key = id(status_msg)
    last = _dl_progress._last.get(key, 0.0)
    if now - last < 1.5 and current < total:
        return
    _dl_progress._last[key] = now

    percentage = (current / total * 100.0) if total else 0.0
    elapsed = now - start
    speed = (current / elapsed) if elapsed > 0 else 0.0
    remaining = total - current
    eta = (remaining / speed) if speed > 0 else 0.0
    bar = _progress_bar(percentage)
    text = (
        f"📥 Downloading...\n\n"
        f"{bar} {percentage:.1f}%\n"
        f"⚡ {_format_size(speed)}/s\n"
        f"⏳ ETA: {_format_duration(eta)}\n"
        f"📦 {_format_size(current)} / {_format_size(total)}"
    )
    try:
        await status_msg.edit_text(text)
    except FloodWait as fw:
        await asyncio.sleep(fw.value)
    except Exception:
        pass


async def _ul_progress(current: int, total: int, msg: Message, status_msg: Message, start: float):
    now = time.time()
    if not hasattr(_ul_progress, "_last"):
        _ul_progress._last = {}
    key = id(status_msg)
    last = _ul_progress._last.get(key, 0.0)
    if now - last < 1.5 and current < total:
        return
    _ul_progress._last[key] = now

    percentage = (current / total * 100.0) if total else 0.0
    elapsed = now - start
    speed = (current / elapsed) if elapsed > 0 else 0.0
    remaining = total - current
    eta = (remaining / speed) if speed > 0 else 0.0
    bar = _progress_bar(percentage)
    text = (
        f"📤 Uploading to Telegram...\n\n"
        f"{bar} {percentage:.1f}%\n"
        f"⚡ {_format_size(speed)}/s\n"
        f"⏳ ETA: {_format_duration(eta)}\n"
        f"📦 {_format_size(current)} / {_format_size(total)}"
    )
    try:
        await status_msg.edit_text(text)
    except FloodWait as fw:
        await asyncio.sleep(fw.value)
    except Exception:
        pass


class SupremeTransformBot:

    def __init__(self):
        self.app = Client(
            name="supreme_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=16,
            max_concurrent_transmissions=8,
            workdir=str(BASE_DIR),
        )
        self.active_jobs: Dict[int, Dict[str, Any]] = {}
        self._register_handlers()

    def _register_handlers(self):

        @self.app.on_message(filters.command("start"))
        async def start_cmd(client, message):
            text = (
                "🎬 Supreme Video Transform Bot v3.0\n\n"
                "I transform videos to bypass automated copyright detection while preserving the ORIGINAL AUDIO for your viewers.\n\n"
                "✨ Features:\n"
                "✅ Original audio preserved as primary (92-95% audible)\n"
                "✅ Subtle BGM layer (5-8%) for fingerprint bypass only\n"
                "✅ Randomized Supreme Mode — unique fingerprint per video\n"
                "✅ Files up to 2GB\n"
                "✅ 7-layer AI anti-detection: spatial + temporal + noise + hash + chroma + spectrogram + GOP\n\n"
                "📤 How to use:\n"
                "1. Send any video (MP4, AVI, MKV, MOV, WEBM)\n"
                "2. I download → transform → upload back\n"
                "3. All single-pass FFmpeg\n\n"
                "⚙️ /settings — View parameters\n"
                "📊 /status — Check active jobs"
            )
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                        InlineKeyboardButton("📊 Status", callback_data="status"),
                    ]
                ]
            )
            await message.reply_text(text, reply_markup=keyboard)

        @self.app.on_message(filters.command("status"))
        async def status_cmd(client, message):
            if not self.active_jobs:
                await message.reply_text("📊 No active jobs.")
                return
            lines = ["📊 Active Jobs:\n"]
            for chat_id, job in self.active_jobs.items():
                status = job.get("status", "unknown")
                tid = job.get("task_id", "")
                lines.append(f"├ Chat {chat_id} | {status} | {tid}")
            await message.reply_text("\n".join(lines))

        @self.app.on_message(filters.command("settings"))
        async def settings_cmd(client, message):
            text = (
                "⚙️ Randomized Supreme Mode Parameters:\n\n"
                "├ 🔍 Zoom scale: 1.05 – 1.12 (random)\n"
                "├ ☀️ Brightness: 0.03 – 0.08 (random)\n"
                "├ 🎚 Contrast: 0.01 – 0.05 (random)\n"
                "├ 🎨 Saturation: -0.08 – -0.02 (random)\n"
                "├ 🔁 Mirror (hflip): True/False (random)\n"
                "├ ⚡ Speed factor: 1.02 – 1.08 (random)\n"
                "├ 🎵 Pitch semitones: -2.5 – -0.5 (random)\n"
                "├ 🔊 BGM volume: 0.05 – 0.08 (random)\n"
                "├ 📺 Noise strength: 6 – 15 (random)\n"
                "├ 🎞 GOP size: 12 – 250 (random)\n"
                "├ 🌀 Chroma shift: 0 – 3 px (random)\n"
                "├ 🎨 Color channel mixer: ±0.03 (random)\n"
                "└ 🎯 Target FPS: nearest standard (auto)\n\n"
                "🧹 Metadata fully wiped\n"
                "🤖 7-layer AI anti-detection active"
            )
            await message.reply_text(text)

        @self.app.on_callback_query()
        async def handle_callback(client, callback):
            data = callback.data or ""
            if data == "settings":
                text = (
                    "⚙️ Randomized Supreme Mode Parameters:\n\n"
                    "├ 🔍 Zoom scale: 1.05 – 1.12 (random)\n"
                    "├ ☀️ Brightness: 0.03 – 0.08 (random)\n"
                    "├ 🎚 Contrast: 0.01 – 0.05 (random)\n"
                    "├ 🎨 Saturation: -0.08 – -0.02 (random)\n"
                    "├ 🔁 Mirror (hflip): True/False (random)\n"
                    "├ ⚡ Speed factor: 1.02 – 1.08 (random)\n"
                    "├ 🎵 Pitch semitones: -2.5 – -0.5 (random)\n"
                    "├ 🔊 BGM volume: 0.05 – 0.08 (random)\n"
                    "├ 📺 Noise strength: 6 – 15 (random)\n"
                    "├ 🎞 GOP size: 12 – 250 (random)\n"
                    "├ 🌀 Chroma shift: 0 – 3 px (random)\n"
                    "├ 🎨 Color channel mixer: ±0.03 (random)\n"
                    "└ 🎯 Target FPS: nearest standard (auto)\n\n"
                    "🧹 Metadata fully wiped\n"
                    "🤖 7-layer AI anti-detection active"
                )
                try:
                    await callback.message.edit_text(text)
                except Exception:
                    await callback.message.reply_text(text)
                await callback.answer()
            elif data == "status":
                if not self.active_jobs:
                    text = "📊 No active jobs."
                else:
                    lines = ["📊 Active Jobs:\n"]
                    for chat_id, job in self.active_jobs.items():
                        status = job.get("status", "unknown")
                        tid = job.get("task_id", "")
                        lines.append(f"├ Chat {chat_id} | {status} | {tid}")
                    text = "\n".join(lines)
                try:
                    await callback.message.edit_text(text)
                except Exception:
                    await callback.message.reply_text(text)
                await callback.answer()
            else:
                await callback.answer()

        @self.app.on_message(filters.video | filters.document)
        async def handle_video(client, message):
            chat_id = message.chat.id

            if chat_id in self.active_jobs:
                await message.reply_text("⚠️ You already have an active job. Please wait until it finishes.")
                return

            file_size = 0
            ext = ".mp4"
            if message.video:
                file_size = message.video.file_size or 0
                fname = message.video.file_name or ""
                if fname and "." in fname:
                    ext = "." + fname.rsplit(".", 1)[-1].lower()
                else:
                    ext = ".mp4"
            elif message.document:
                mime = (message.document.mime_type or "").lower()
                fname = message.document.file_name or ""
                if not mime.startswith("video"):
                    valid_exts = (".mp4", ".avi", ".mkv", ".mov", ".webm")
                    if not fname.lower().endswith(valid_exts):
                        await message.reply_text("⚠️ Please send a valid video file (MP4, AVI, MKV, MOV, WEBM).")
                        return
                file_size = message.document.file_size or 0
                if fname and "." in fname:
                    ext = "." + fname.rsplit(".", 1)[-1].lower()
                else:
                    ext = ".mp4"
            else:
                await message.reply_text("⚠️ Unsupported file.")
                return

            if file_size and file_size > MAX_FILE_SIZE:
                await message.reply_text(
                    f"⚠️ File too large: {_format_size(file_size)}.\nMaximum allowed: {_format_size(MAX_FILE_SIZE)}."
                )
                return

            task_id = uuid.uuid4().hex[:8]
            workspace = tempfile.mkdtemp(prefix=f"supreme_{task_id}_", dir=str(DOWNLOAD_DIR))

            self.active_jobs[chat_id] = {
                "status": "queued",
                "task_id": task_id,
                "workspace": workspace,
                "ext": ext,
            }

            asyncio.create_task(self._process_video(client, message, chat_id, task_id))
            await message.reply_text("📥 Queued...")

    async def _process_video(self, client, message, chat_id, task_id):
        job = self.active_jobs.get(chat_id, {})
        workspace = job.get("workspace")
        ext = job.get("ext", ".mp4")
        status_msg = None

        input_path = os.path.join(workspace, f"input_{task_id}{ext}")
        output_path = os.path.join(workspace, f"output_{task_id}.mp4")

        try:
            status_msg = await message.reply_text("📥 Starting download...")

            # PHASE 1 — DOWNLOAD
            job["status"] = "downloading"
            start_dl = time.time()
            downloaded = await client.download_media(
                message,
                file_name=input_path,
                progress=_dl_progress,
                progress_args=(message, status_msg, start_dl),
            )
            if not downloaded or not os.path.exists(input_path):
                if downloaded and os.path.exists(downloaded):
                    input_path = downloaded
                else:
                    await status_msg.edit_text("❌ Download failed.")
                    return

            # PHASE 2 — TRANSFORM
            job["status"] = "processing"
            try:
                await status_msg.edit_text("⚙️ Transforming...")
            except Exception:
                pass

            bgm_path = pick_random_bgm()

            async def _progress(text, pct):
                try:
                    await status_msg.edit_text(text)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                except Exception:
                    pass

            async with ffmpeg_semaphore:
                success = await supreme_transform_video(
                    input_path,
                    output_path,
                    new_bgm_path=bgm_path,
                    progress_callback=_progress,
                    task_id=task_id,
                )

            if not success or not os.path.exists(output_path):
                await status_msg.edit_text("❌ Transform failed.")
                return

            # PHASE 3 — UPLOAD
            job["status"] = "uploading"
            try:
                await status_msg.edit_text("📤 Uploading to Telegram...")
            except Exception:
                pass

            out_size = os.path.getsize(output_path)
            caption = (
                "🎥 Supreme Transformed Video ✅\n\n"
                "**Applied protections:**\n"
                "├ 🧹 Metadata wiped\n"
                "├ 🎨 Visual hash altered (zoom+crop+color+noise)\n"
                "├ 🎵 **Original audio preserved** (92-95% dominant)\n"
                "├ 🔊 Subtle BGM layer (5-8%) for fingerprint change\n"
                "├ 🌀 Frame hash broken (invisible per-frame marker)\n"
                "├ 🎚 Perceptual hash destroyed (chroma shift)\n"
                "└ 🤖 AI anti-detection: 7 layers active\n\n"
                f"📦 {_format_size(out_size)} | ⚙️ Randomized Supreme Mode"
            )

            start_ul = time.time()
            try:
                await client.send_video(
                    chat_id,
                    video=output_path,
                    caption=caption,
                    parse_mode=enums.ParseMode.MARKDOWN,
                    supports_streaming=True,
                    progress=_ul_progress,
                    progress_args=(message, status_msg, start_ul),
                )
            except Exception as e:
                logger.error(f"[{task_id}] send_video failed, fallback to document: {e}")
                start_ul = time.time()
                await client.send_document(
                    chat_id,
                    document=output_path,
                    caption=caption,
                    parse_mode=enums.ParseMode.MARKDOWN,
                    progress=_ul_progress,
                    progress_args=(message, status_msg, start_ul),
                )

            try:
                await status_msg.edit_text("✅ Transform complete! Video sent above.")
            except Exception:
                pass

        except FloodWait as fw:
            logger.error(f"[{task_id}] FloodWait: {fw.value}")
            await asyncio.sleep(fw.value)
        except Exception as e:
            logger.exception(f"[{task_id}] Processing error: {e}")
            if status_msg:
                try:
                    await status_msg.edit_text(f"❌ Error: {e}")
                except Exception:
                    pass
        finally:
            # CLEANUP
            self.active_jobs.pop(chat_id, None)
            if workspace:
                shutil.rmtree(workspace, ignore_errors=True)

    async def start(self):
        logger.info("Starting...")
        await self.app.start()
        me = await self.app.get_me()
        logger.info(f"Bot online: @{me.username}")
        await asyncio.Event().wait()

    async def stop(self):
        await self.app.stop()


async def main():
    global API_ID, API_HASH, BOT_TOKEN

    if not API_ID or not API_HASH or not BOT_TOKEN:
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    os.environ.setdefault(key, val)
            except Exception as e:
                logger.error(f"Failed to load .env: {e}")

            try:
                API_ID = int(os.environ.get("API_ID", "0"))
            except (TypeError, ValueError):
                API_ID = 0
            API_HASH = os.environ.get("API_HASH", "")
            BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

    if not API_ID or not API_HASH or not BOT_TOKEN:
        print(
            "ERROR: API_ID, API_HASH, and BOT_TOKEN must be set.\n"
            "Set them as environment variables or create a .env file in this folder:\n\n"
            "  API_ID=1234567\n"
            "  API_HASH=your_api_hash\n"
            "  BOT_TOKEN=123456:your_bot_token\n\n"
            "Get API_ID / API_HASH from https://my.telegram.org and BOT_TOKEN from @BotFather."
        )
        sys.exit(1)

    # Verify ffmpeg / ffprobe are available, otherwise transforms will silently fail.
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            print(
                f"ERROR: '{tool}' was not found on PATH. Install FFmpeg first.\n"
                "  Debian/Ubuntu: sudo apt-get install -y ffmpeg\n"
                "  macOS (brew):  brew install ffmpeg"
            )
            sys.exit(1)

    bot = SupremeTransformBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        pass
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
