# Oura Agent — Setup & Deployment Guide

A personalised daily coach that reads your Oura ring, Google Calendar, and Notion,
then messages you on Telegram throughout the day.

---

## What you'll need (one-time setup, ~45 minutes)

1. **A server to run it on** — see Hosting section below
2. **Oura Personal Access Token**
3. **Anthropic API key**
4. **Telegram bot token + your chat ID**
5. **Notion integration token**
6. **Google Calendar API credentials**

---

## Step 1 — Hosting (recommended: Hetzner CX22)

The agent runs 24/7, so it needs an always-on Linux server.

**Best option: Hetzner Cloud CX22** (~€4.50/month, Berlin or Falkenstein)
- Go to https://hetzner.com/cloud → create an account → New Server
- Location: Falkenstein (closest to UK) or Helsinki
- Image: Ubuntu 24.04
- Type: CX22 (2 vCPU, 4GB RAM — plenty)
- Add your SSH public key (or create one: `ssh-keygen -t ed25519`)
- No backups needed for now, but consider enabling later

Once created, SSH in:
```bash
ssh root@YOUR_SERVER_IP
```

---

## Step 2 — Server setup

```bash
# Update and install Python
apt update && apt upgrade -y
apt install -y python3.12 python3.12-venv python3-pip git tmux

# Create a non-root user (optional but good practice)
adduser shaun
usermod -aG sudo shaun
su - shaun

# Clone or upload the agent
mkdir -p ~/oura-agent && cd ~/oura-agent
# Then upload your files (scp or git)
```

---

## Step 3 — Get your API credentials

### 3a. Oura Personal Access Token
1. Go to https://cloud.ouraring.com/personal-access-tokens
2. Click "Create New Personal Access Token"
3. Give it a name (e.g. "Daily Agent")
4. Copy the token — you won't see it again

### 3b. Anthropic API Key
1. Go to https://console.anthropic.com
2. Settings → API Keys → Create Key
3. Copy it

### 3c. Telegram Bot + Chat ID
1. Open Telegram, search for `@BotFather`
2. Send `/newbot` → follow the prompts → copy the token (looks like `123456:ABC-DEF...`)
3. Start a chat with your new bot (search for it by the name you gave it)
4. Get your chat ID: open https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates in a browser
   after sending the bot any message. Look for `"chat":{"id":XXXXXXXXX}` — that's your chat ID.

### 3d. Notion Integration Token
1. Go to https://www.notion.so/my-integrations
2. Click "New integration" → give it a name (e.g. "Oura Agent") → select your workspace
3. Capabilities: Read content, Read user info (no write access needed for now)
4. Copy the "Internal Integration Token"
5. **Important**: In Notion, open your Tasks database and "My Day" page → click "..." → 
   "Connect to" → select your integration. Do this for both pages.

### 3e. Google Calendar API
1. Go to https://console.cloud.google.com
2. Create a new project (e.g. "Oura Agent")
3. Enable the Google Calendar API: APIs & Services → Enable APIs → search "Calendar"
4. Create credentials: APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
5. Application type: Desktop app
6. Download the JSON → rename to `credentials.json` → upload to your server
7. First run will open a browser to authenticate → this creates `token.pickle` for future use

---

## Step 4 — Install and configure

```bash
cd ~/oura-agent

# Create virtualenv
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.template .env
nano .env  # Fill in all your credentials
```

Your `.env` should look like:
```
OURA_PERSONAL_ACCESS_TOKEN=pat_xxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUVwxyz
TELEGRAM_CHAT_ID=123456789
NOTION_API_KEY=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_TASKS_DB_ID=1c9aa925b9f681ad8085d1b16c0e3785
NOTION_MY_DAY_PAGE_ID=1c9aa925b9f681a99ddde2714bac1344
GOOGLE_CREDENTIALS_PATH=./credentials.json
```

---

## Step 5 — First run and Google auth

The first time you run the agent, it needs to authenticate with Google Calendar.
This must be done locally (on your laptop, not the server) if you don't have a browser on the server.

**On your laptop:**
```bash
# Clone the repo locally too
cd ~/oura-agent
pip install -r requirements.txt
cp .env.template .env && nano .env  # fill in credentials

# Run just the auth flow
python3 -c "from src.context import fetch_calendar_events; print(fetch_calendar_events())"
# This will open a browser window to authenticate — sign in with your Google account
# It creates token.pickle — upload this to the server:
scp token.pickle shaun@YOUR_SERVER_IP:~/oura-agent/
```

---

## Step 6 — Run the agent

```bash
# On the server, inside ~/oura-agent with venv activated:
source venv/bin/activate

# Test it first
python3 -c "from src.oura import fetch_daily_snapshot; import json; print(json.dumps(fetch_daily_snapshot(), indent=2))"

# Run with tmux (stays alive after you disconnect)
tmux new -s agent
python3 main.py
# Detach: Ctrl+B then D
# Reattach later: tmux attach -t agent
```

---

## Step 7 — Make it survive reboots (systemd service)

```bash
# Create the service file
sudo nano /etc/systemd/system/oura-agent.service
```

Paste this (adjust paths):
```ini
[Unit]
Description=Oura Daily Agent
After=network.target

[Service]
Type=simple
User=shaun
WorkingDirectory=/home/shaun/oura-agent
Environment=PATH=/home/shaun/oura-agent/venv/bin
ExecStart=/home/shaun/oura-agent/venv/bin/python3 main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable oura-agent
sudo systemctl start oura-agent
sudo systemctl status oura-agent  # check it's running

# View logs
journalctl -u oura-agent -f
```

---

## Daily touchpoints

| Time  | Touchpoint   | Purpose |
|-------|-------------|---------|
| 05:30 | 🌅 Morning   | Sleep debrief + readiness + gym guidance |
| 12:30 | ☀️ Midday    | Energy + caffeine check-in |
| 16:00 | 🌤 Afternoon | Productivity + wind-down awareness |
| 20:00 | 🌙 Evening   | Wind-down trigger + melatonin reminder |
| 22:30 | 🌑 Night*    | Only fires if you have late calendar events |

*\*Conditional — checks your calendar before firing*

## Telegram commands

| Command     | What it does |
|-------------|-------------|
| `/status`   | Instant biometric snapshot |
| `/busy`     | Tell agent you're busy — reduces messages |
| `/notes`    | See what the agent has logged today |
| `/trends`   | 7-day readiness/sleep trend |
| Just type anything | Agent replies in context |

---

## Costs

| Service | Cost |
|---------|------|
| Hetzner CX22 | ~€4.50/month |
| Anthropic API | ~$3–8/month at this message volume |
| Everything else | Free |
| **Total** | **~£8–10/month** |

---

## Troubleshooting

**Agent not sending messages at scheduled times?**
- Check `journalctl -u oura-agent -f` for errors
- Make sure server timezone matches: `timedatectl set-timezone Europe/London`

**Oura data missing?**
- Wear the ring consistently — baselines need ~2 weeks of data
- Check your PAT hasn't expired at https://cloud.ouraring.com/personal-access-tokens

**Google Calendar auth expired?**
- Delete `token.pickle`, re-run auth flow on your laptop, re-upload

**Telegram not receiving messages?**
- Make sure you've sent the bot at least one message first (bots can't initiate with strangers)
- Verify TELEGRAM_CHAT_ID matches what getUpdates returns
