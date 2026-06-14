# Manu's Personal AI Coaching Agent

Your personal AI oracle for sleep, energy, HRV recovery, and training optimization. Powered by Claude API + Oura ring + Telegram.

## Features

- **Smart Coaching**: Claude analyzes your Oura data and sends personalized messages 5x daily
- **Two-way Messaging**: Telegram replies integrate into the coaching loop
- **Calendar Aware**: Respects your calendar to avoid interrupting meetings
- **Task Integration**: Pulls from Notion to understand your priorities
- **Adaptive Tone**: Direct/motivational/Socratic depending on context
- **Memory**: Learns patterns over time (caffeine effects, sleep timing, HRV trends)

## Goals (Priority Order)

1. **Sleep Quality** (master goal) — 21:00 bed, 05:00 wake, 7.5-8.5h, >85% efficiency
2. **Daytime Energy** — eliminate caffeine dependency (0-1 coffees/day)
3. **HRV/Recovery** — use HRV as master readiness signal
4. **Physique & Strength** — daily gym (Chest+Tris → Back+Bis → Legs+Core)

## Daily Touchpoints

- **05:30**: Morning checkpoint (post-gym energy pulse)
- **12:30**: Midday energy check (caffeine tracking)
- **16:00**: Afternoon slump prevention
- **20:00**: Evening wind-down trigger
- **23:00**: Conditional night check (only if awake)
- **Reactive**: When Oura detects something remarkable

## Installation

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/oura-agent.git
cd oura-agent
```

### 2. Create Python environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up credentials

Copy the env template:
```bash
cp .env.template .env
```

Then fill in each credential:

#### A. Oura Personal Access Token
1. Go to https://cloud.ouraring.com/personal-access-tokens
2. Create a new token
3. Paste into `.env`: `OURA_PERSONAL_ACCESS_TOKEN=pat_...`

#### B. Anthropic API Key
1. Go to https://console.anthropic.com/account/keys
2. Create a new API key
3. Paste into `.env`: `ANTHROPIC_API_KEY=sk-ant-...`

#### C. Telegram Bot Token + Chat ID
1. Message @BotFather on Telegram
2. Create a new bot: `/newbot`
3. Get your token (looks like `1234567890:ABCdefGHIjklMNOpqrSTUVwxyz`)
4. Paste into `.env`: `TELEGRAM_BOT_TOKEN=...`
5. Message your bot to yourself
6. Run `curl https://api.telegram.org/botYOUR_TOKEN/getUpdates` and find your chat ID
7. Paste into `.env`: `TELEGRAM_CHAT_ID=123456789`

#### D. Notion Integration Token
1. Go to https://notion.so/my-integrations
2. Create a new integration
3. Copy the "Internal Integration Token"
4. Paste into `.env`: `NOTION_API_KEY=secret_...`

#### E. Google Calendar (Optional)
1. Go to https://console.cloud.google.com
2. Create a project
3. Enable Google Calendar API
4. Create OAuth 2.0 Desktop credentials (Download as JSON)
5. Save as `credentials.json` in the agent directory
6. Update `.env`: `GOOGLE_CREDENTIALS_PATH=./credentials.json`
7. When you first run the agent, it will open a browser for OAuth auth
8. The token will be saved as `token.pickle` for future runs

### 5. Update Notion IDs (already in `.env.template`)
The Notion database IDs are already filled in your `.env.template` (from the project setup).

## Running Locally (Testing)

```bash
python main.py
```

The agent will:
- Start listening for Telegram messages
- Schedule daily coaching messages
- Log everything to `agent.db` (SQLite)

Test a message in Telegram: your bot will respond!

## Deploying to Hetzner VPS

### Prerequisites
- Hetzner account
- Server IP address
- SSH access (or web console)

### Step-by-step

1. **SSH into server**
   ```bash
   ssh root@YOUR_SERVER_IP
   ```

2. **Update system & install tools**
   ```bash
   apt update && apt upgrade -y
   apt install -y python3 python3-venv python3-pip tmux git
   timedatectl set-timezone Europe/London
   ```

3. **Clone the agent repo**
   ```bash
   cd ~
   git clone https://github.com/yourusername/oura-agent.git
   cd oura-agent
   ```

4. **Set up Python environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Configure .env**
   ```bash
   cp .env.template .env
   nano .env  # Fill in all credentials
   ```

6. **Add Google credentials (if using Calendar)**
   ```bash
   # On your Mac, create credentials.json and upload it:
   scp credentials.json root@YOUR_SERVER_IP:~/oura-agent/
   ```

7. **Run in background with tmux**
   ```bash
   tmux new-session -d -s coach "cd ~/oura-agent && source venv/bin/activate && python main.py"
   ```

8. **Check logs**
   ```bash
   tmux attach-session -t coach
   # Press Ctrl+B then D to detach (keeps running)
   ```

### Keeping it running (systemd service)

Create `/etc/systemd/system/coach.service`:
```bash
sudo nano /etc/systemd/system/coach.service
```

Paste:
```ini
[Unit]
Description=Manu's AI Coaching Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/oura-agent
Environment="PATH=/root/oura-agent/venv/bin"
ExecStart=/root/oura-agent/venv/bin/python /root/oura-agent/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable coach
sudo systemctl start coach
sudo systemctl status coach
```

## Telegram Commands

- `/status` — Today's snapshot (readiness, sleep, efficiency)
- `/busy` — Pause coaching for 1 hour
- `/available` — Resume messaging
- `/trends` — Weekly pattern analysis
- Plain text reply — Agent responds conversationally

## Monitoring

Agent logs to `agent.db` (SQLite). View recent messages:
```bash
sqlite3 agent.db "SELECT * FROM messages ORDER BY timestamp DESC LIMIT 10;"
```

View daily data:
```bash
sqlite3 agent.db "SELECT * FROM daily_logs ORDER BY date DESC LIMIT 7;"
```

## Troubleshooting

### "Can't connect to Telegram"
- Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`
- Verify you've messaged your bot at least once

### "Oura API error"
- Check `OURA_PERSONAL_ACCESS_TOKEN` is valid
- Verify you're on https://cloud.ouraring.com/personal-access-tokens (not the old dashboard)

### "Notion permissions error"
- Ensure the Notion integration is shared with your database and page
- Double-check `NOTION_TASKS_DB_ID` and `NOTION_MY_DAY_PAGE_ID`

### Google Calendar not working
- Delete `token.pickle` and re-run to re-authenticate
- Ensure the OAuth credentials are type "Desktop Application"

## Costs

- **Hetzner VPS**: €9.59/month (CPX22, 2 cores, 4GB RAM)
- **Anthropic API**: ~$0.10-0.50/month (depending on usage)
- **Total**: ~£10-12/month

## What's next?

- After 2-3 weeks, the agent will start offering insights ("I've noticed caffeine after noon → longer sleep onset")
- Patterns go into Notion for long-term review
- Adapt your routine based on what's working
- Update the system prompt in `src/brain.py` if goals change

---

**Built with Claude + Telegram + Oura. Sleep is the master goal.**
