#!/usr/bin/env bash
# Start the Supreme Video Transform Bot.
# Usage: ./start.sh
set -e

cd "$(dirname "$0")"

# 1. Ensure Python dependencies are installed.
if ! python3 -c "import pyrogram" 2>/dev/null; then
    echo "[start] Installing Python dependencies..."
    pip install -r requirements.txt
fi

# 2. Ensure ffmpeg is available.
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "[start] ERROR: ffmpeg not found. Install it with: sudo apt-get install -y ffmpeg"
    exit 1
fi

# 3. Load .env if present (so credentials are available even without export).
if [ -f .env ]; then
    echo "[start] Loading credentials from .env"
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

# 4. Launch the bot.
echo "[start] Launching supreme_bot.py ..."
exec python3 supreme_bot.py
