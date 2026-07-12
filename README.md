# Automated Video Transformer

An advanced, asynchronous Telegram bot designed for heavy, automated video processing and media pipeline management. 

This project utilizes Python, Pyrogram (MTProto), and FFmpeg to perform multi-layered video transformations, metadata modification, and structural video editing directly via Telegram.

## 🚀 Core Features
* **Native Large File Support:** Processes and transfers media files up to 2GB leveraging the Pyrogram MTProto framework.
* **Complex Media Pipeline:** Executes single-pass, multi-layered FFmpeg filter graphs for efficient video rendering.
* **Asynchronous Processing:** Handles concurrent downloads, processing, and uploads without blocking the main event loop.
* **Real-time Status:** Provides live progress tracking for downloads and uploads with speed and ETA calculations.

## 🛠️ Technical Stack
* **Language:** Python 3.9+
* **Framework:** Pyrogram, TgCrypto
* **Engine:** FFmpeg

## ▶️ Running the Bot

1. **Install dependencies** (Python 3.9+ and FFmpeg required):
   ```bash
   pip install -r requirements.txt
   # Debian/Ubuntu: sudo apt-get install -y ffmpeg
   ```
2. **Configure credentials** — copy `.env.example` to `.env` and fill in your values:
   ```bash
   cp .env.example .env
   # then edit .env with your API_ID, API_HASH, BOT_TOKEN
   ```
   Get `API_ID` / `API_HASH` from https://my.telegram.org and `BOT_TOKEN` from [@BotFather](https://t.me/BotFather).
3. **Start the bot**:
   ```bash
   ./start.sh
   # or:  python3 supreme_bot.py
   ```

`start.sh` auto-installs dependencies, verifies FFmpeg, loads `.env`, and launches the bot.
On startup the bot validates credentials and FFmpeg, and prints a clear error if anything is missing.

## 🔒 Security Note
This is a public repository. Do not upload your `.env` file containing `API_ID`, `API_HASH`, or `BOT_TOKEN`. Keep your credentials local and secure.
