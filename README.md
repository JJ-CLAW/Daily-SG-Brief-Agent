# Daily SG Brief Agent

![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot_API-26A5E4?style=flat&logo=telegram&logoColor=white)
![Headlines RSS](https://img.shields.io/badge/Headlines-RSS-F97316?style=flat)
![Personal project](https://img.shields.io/badge/project-personal-orange?style=flat)

A small Python tool that builds a **morning briefing** and sends it to **Telegram** as one HTML message. Each run includes:

- **Headlines** from an RSS feed (default: [Google News Singapore EN](https://news.google.com/rss?hl=en-SG&gl=SG&ceid=SG:en))
- **Singapore weather** (scraped from a public source used in code)
- **Thought for today** — one line from `motivations.txt`, chosen deterministically for that calendar date in **Asia/Singapore** (same line all day)

## Requirements

- Python 3.10+ recommended
- Dependencies (see `requirements.txt`): **httpx**, **feedparser**, **python-dotenv**, **APScheduler**, **tzdata**
- A Telegram **bot token** from [@BotFather](https://t.me/BotFather)
- Your **user** chat id (or a group/channel id the bot may post to).  
  **Important:** `TELEGRAM_CHAT_ID` must not be another bot’s id — Telegram returns *“bots can’t send messages to bots”*.

## Setup

1. Clone or copy this repository and enter the project directory.

2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   # source .venv/bin/activate     # macOS / Linux
   pip install -r requirements.txt
   ```

   `tzdata` is listed so `Asia/Singapore` works on Windows without extra OS packages.

3. Copy `.env.example` to `.env` and set:

   | Variable | Required | Description |
   |----------|----------|-------------|
   | `TELEGRAM_BOT_TOKEN` | Yes | Bot token from BotFather |
   | `TELEGRAM_CHAT_ID` | Yes | Chat id from [getUpdates](https://core.telegram.org/bots/api#getupdates) after **you** message **your** bot from your account |
   | `MOTIVATIONS_FILE` | No | Path to quotes file (default: `motivations.txt` in project root) |
   | `NEWS_RSS_URL` | No | Override RSS URL |
   | `HEADLINE_COUNT` | No | Number of headlines (default `5`) |
   | `DAILY_BRIEF_ENV` | No | Path to an alternate `.env` file |

4. Optional: edit `motivations.txt` — one quote per line; `#` comments and leading `- ` / `• ` are supported.

## Usage

Send one brief immediately (needs network):

```bash
python -m brief_agent once
```

Run a **blocking** scheduler that sends every day at **09:30 Asia/Singapore**:

```bash
python -m brief_agent serve
```

Stop with `Ctrl+C`. For production you might run `serve` under a process manager, or use OS scheduling (below).

## Windows Task Scheduler

`scripts/register-windows-task.ps1` registers a daily task at **09:30 in the PC’s local time zone**, running `python -m brief_agent once`. That is **not** the same as 09:30 SGT if the machine is elsewhere.

For **09:30 Singapore time** regardless of where the PC lives, use `python -m brief_agent serve` instead.

Run the script from PowerShell (adjust execution policy if needed):

```powershell
.\scripts\register-windows-task.ps1
```

## Project structure

| Path | Role |
|------|------|
| `brief_agent/` | Package: fetch news/weather, format message, Telegram send |
| `brief_agent/__main__.py` | CLI entry (`once`, `serve`) |
| `motivations.txt` | Daily quote pool |
| `.env` | Secrets and options (not committed; see `.gitignore`) |

## What I learned

Overall agent building and local deployment for simple tasks. Built on basic web scraping from earlier projects to ship an agent that surfaces top news in Singapore and worldwide. Not every integration needs a paid API key—RSS and a small scrape are enough for a first version. Having the brief land in Telegram, which I already use daily, made it stick.

- **Telegram `chat_id` is easy to get wrong.** It must identify the *recipient* (your user, a group, or a channel), not another bot. The API rejects bot-to-bot delivery with a clear 403.
- **HTTP client errors can leak secrets.** Default `httpx` traces include the full URL, which embeds the bot token. It is safer to handle failed `sendMessage` responses explicitly and surface only status and Telegram’s `description`.
- **`ZoneInfo("Asia/Singapore")` needs data on Windows.** Shipping `tzdata` in `requirements.txt` avoids “no time zone found” on machines without IANA zone data.
- **Scheduling has two meanings of “09:30”.** A Windows daily task uses the PC’s local clock; `brief_agent serve` uses a fixed `Asia/Singapore` cron. Pick one deliberately if you care which wall-clock the brief follows.
- **RSS plus scraping keeps the stack small.** Headlines come from a feed without a news API key; weather uses a simple HTTP fetch and parsing, which is enough for a personal brief.

## Troubleshooting

- **Missing token / chat id** — Fill `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`.
- **403 / bots can’t send messages to bots** — Use your personal user `chat.id`, not a bot account.
- **Empty or broken headlines** — Check network, RSS URL, or rate limits on the feed provider.
- Errors from Telegram are raised as `RuntimeError` with HTTP status and API `description` when available (the bot token is not repeated in that message).

## License

No license file is included in this repository; add one if you distribute the project.
