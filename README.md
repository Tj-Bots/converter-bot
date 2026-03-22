# 🚀 Advanced Telegram File & Video Converter Bot

A high-performance, feature-rich Telegram bot built with **Pyrofork**. This bot is designed for seamless file management, media conversion, and advanced user personalization.

---

## ✨ Key Features

<details>
<summary><b>📂 Core Media Management</b></summary>

- **Fast Renaming:** Rename any file or video with full extension support.
- **Media Conversion:** Convert **Video ↔️ Document** on the fly.
- **Thumbnail Support:** Save custom thumbnails (`/viewthumb`, `/delthumb`) for all your future uploads.
- **Screenshot Generation:** Automatically extract up to 10 screenshots from videos (configurable in settings).
</details>

<details>
<summary><b>🎨 Advanced Personalization</b></summary>

- **Custom Captions:** Powerful HTML caption engine with dynamic variables:
  - `{filename}`: The name of the processed file.
  - `{filesize}`: Human-readable size (e.g., 1.5 GB).
- **Flexible Modes:**
  - `🎥 Video`: Always upload as streamable video.
  - `📁 File`: Always upload as a document.
  - `🔄 Swap`: Automatically switch (Video to File, File to Video).
  - `❓ Ask`: Prompt for action on every file.
</details>

<details>
<summary><b>⭐ Premium & Monetization System</b></summary>

- **Tiered Plans:**
  - **🎯 Free:** 10 daily conversions, 2GB max size, 1 concurrent task, 60s cooldown.
  - **🧪 Test:** (Trial) 10 daily conversions, 4GB max size, 2 concurrent tasks, no cooldown.
  - **🥇 Gold:** 20 daily conversions, 4GB max size, 2 concurrent tasks.
  - **👑 Ultra:** 50 daily conversions, Unlimited size, 3 concurrent tasks.
- **Redeem System:** Integrated `/redeem` command for activating premium plans via codes.
- **Daily Limits:** Intelligent tracking and automated daily reset at 00:00 UTC.
</details>

<details>
<summary><b>📊 Performance & Monitoring</b></summary>

- **Live Progress:** Detailed progress bars for both downloading and uploading.
- **Server Health:** Real-time monitoring of CPU, RAM, Disk, and Task Load (`/status`).
- **Concurrent Tasks:** Advanced locking system to manage multiple tasks per user.
- **Premium Userbot:** Integrated Session String support for bypassing Telegram's 2GB upload limit (up to 4GB/Unlimited).
</details>

---

## 🛠 Tech Stack

- **Language:** Python 3.13+
- **Core:** [Pyrofork](https://github.com/himeko-org/pyrofork)
- **Metadata:** [Hachoir](https://github.com/vstinner/hachoir)
- **Media Processing:** [FFmpeg](https://ffmpeg.org/)
- **System monitoring:** `psutil`
- **Database:** Local JSON persistence (`users_db.json`)

---

## 🚀 Commands Guide

### 👤 User Commands
- `/start` - Launch the bot and main menu.
- `/help` - Comprehensive guide for Thumbnails, Captions, and Redeem.
- `/settings` - Configure Mode, Rename behavior, and Screenshot count.
- `/plans` - View subscription details and limits.
- `/status` - View active tasks and server performance.
- `/set_cap` / `/del_cap` - Manage custom caption templates.
- `/viewthumb` / `/delthumb` - Manage custom thumbnails.
- `/redeem <code>` - Activate premium access.
- `/cancel <task_id>` - Stop a specific active task.

### 👑 Admin Commands (`ADMIN_ID` only)
- `/admin` - Master control panel with full user/plan statistics.
- `/broadcast` - Send announcements (Copy/Forward modes) to all users.
- `/gencodes <count> <duration> [plan]` - Generate unique redeem codes (e.g., `/gencodes 5 30d gold`).
- `/redeem_stats` - View used vs available redeem codes.
- `/add_plan <uid> <plan> <duration>` - Manually grant premium access.
- `/remove_plan <uid>` - Revoke premium access.
- `/plan_list` - List active premium users.
- `/users` / `/allban` - Manage user database and bans.
- `/ban` / `/unban <uid>` - Restrict user access.
- `/restart` - Reboot the bot remotely.
- `/cancelall` - Stop all active tasks on the server.

---

## 🐋 Docker & VPS Deployment

<details>
<summary><b>🚀 Run with Docker (Recommended)</b></summary>

1.  **Build and Start:**
    ```bash
    docker compose up -d --build
    ```

2.  **View Logs:**
    ```bash
    docker compose logs -f
    ```

3.  **Stop:**
    ```bash
    docker compose down
    ```
</details>

<details>
<summary><b>🖥️ Run on VPS (Manual Setup)</b></summary>

1.  **Install dependencies:**
    ```bash
    sudo apt update && sudo apt install -y python3-pip ffmpeg
    ```

2.  **Clone and install requirements:**
    ```bash
    git clone https://github.com/Tj-Bots/converter-bot.git
    cd converter-bot
    pip install -r requirements.txt
    ```

3.  **Run in background (screen/tmux):**
    ```bash
    screen -S converter-bot
    python3 main.py
    ```
</details>

---

## ⚙️ Configuration (.env)

| Variable | Description |
| :--- | :--- |
| `API_ID` | Telegram API ID from my.telegram.org |
| `API_HASH` | Telegram API Hash from my.telegram.org |
| `BOT_TOKEN` | Bot token from @BotFather |
| `ADMIN_ID` | Numerical ID of the bot administrator |
| `DUMP_CHANNEL` | Channel ID for file storage (Premium/Large files) |
| `SESSION_STRING` | (Optional) Pyrogram session for Premium features |

---

**Developed with ❤️ by [𝑻𝒉𝒆 𝑱𝒐𝒌𝒆𝒓🃏](https://t.me/The_Joker121_bot)**
