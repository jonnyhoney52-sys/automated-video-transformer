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

## 🔒 Security Note
This is a public repository. Do not upload your `.env` file containing `API_ID`, `API_HASH`, or `BOT_TOKEN`. Keep your credentials local and secure.
