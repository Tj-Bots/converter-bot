# 🚀 Advanced Telegram File & Video Converter Bot

A powerful, high-performance Telegram bot built with **Pyrofork** (a modern Pyrogram fork). This bot allows users to rename files, change thumbnails, and convert between video and document formats with advanced features like custom captions and screenshots.

---

## ✨ Key Features

<details>
<summary><b>📂 File & Media Management</b></summary>

- **Rename Files:** Custom renaming with original extension preservation.
- **Thumbnail Support:** Set custom thumbnails for all your uploads.
- **Conversion:** Effortlessly convert **Video ↔️ Document**.
- **Large File Support:** Handles files up to **4GB** (with Premium/Userbot session).
</details>

<details>
<summary><b>🎨 Personalization</b></summary>

- **Custom Captions:** Support for HTML tags and dynamic variables (`{filename}`, `{filesize}`).
- **Screenshots:** Automatically generate and send multiple screenshots from videos.
- **Flexible Modes:** Choose between Video, File, Swap, or Ask-on-each-file modes.
</details>

<details>
<summary><b>⭐ Premium & User Management</b></summary>

- **Tiered Plans:** Free, Test, Gold, and Ultra plans with different limits.
- **Redeem System:** Grant premium access via unique redeem codes.
- **Daily Limits:** Intelligent daily conversion tracking and reset.
- **Admin Panel:** Full control over users, bans, plans, and broadcasting.
</details>

<details>
<summary><b>📊 Performance & Stability</b></summary>

- **Real-time Status:** Live progress bars and server performance monitoring (CPU/RAM/Disk).
- **Task Management:** Simultaneous task handling with cancellation support.
- **Database:** Local JSON-based storage for user persistence.
</details>

---

## 🛠 Tech Stack

- **Language:** Python 3.13+
- **Core Library:** [Pyrofork](https://github.com/himeko-org/pyrofork)
- **Metadata:** [Hachoir](https://github.com/vstinner/hachoir)
- **Media Processing:** [FFmpeg](https://ffmpeg.org/)
- **Process Info:** [psutil](https://github.com/giampaolo/psutil)

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/converter-bot.git
   cd converter-bot
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory:
   ```env
   API_ID=your_api_id
   API_HASH=your_api_hash
   BOT_TOKEN=your_bot_token
   ADMIN_ID=your_telegram_id
   DUMP_CHANNEL=your_channel_id
   SESSION_STRING=your_premium_session_string (optional)
   ```

4. **Run the bot:**
   ```bash
   python main.py
   ```

---

## 📜 Commands

- `/start` - Start the bot and see the main menu.
- `/settings` - Configure your personal upload preferences.
- `/plans` - View and upgrade your subscription.
- `/status` - Check active tasks and server health.
- `/set_cap` - Set a custom caption template.
- `/viewthumb` - View your current custom thumbnail.
- `/redeem` - Activate premium using a code.

---

## 👑 Admin Commands

- `/admin` - Open the admin control panel.
- `/broadcast` - Send messages to all users.
- `/gencodes` - Generate unique redeem codes.
- `/ban` / `/unban` - Manage user access.
- `/add_plan` - Manually grant premium to a user.

---

> **Note:** This bot is designed for high-performance file handling. Ensure your server has sufficient disk space for temporary file processing.

---
**Developed with ❤️ by [𝑻𝒉𝒆 𝑱𝒐𝒌𝒆𝒓🃏](https://t.me/The_Joker121_bot)**
