# Telegram Tutor Filtering Bot

A Telegram bot that watches tuition agencies channel and forwards only the listings that match my criteria. It uses Gemini to parse the listing text and Google Mpas to check travel time.

# How it works
1. Listens for new messages in the channels listed in `TARGET_CHANNELS` using Telethon
2. Sends each listing to Gemini, which returns structured JSON: subject, level, rate, online or onsite, and postal code.
3. Applies the filter rules (see below). For onsite listings outside the prime areas, it checks public transit time with Google Maps Distance Matrix API.
4. Forwards matches to my Telegram "Saved Messages".

Listings are processed one at a time, with a 10-second delay, to stay under Gemini's free tier-rate limit.

# Filter Rules

| Rule | Condition |
| --- | --- |
| Subject | Math, Biology, Chemistry or Science |
| Rate | Max hourly rate of at least $60, unless the rate is "tutor to propose" |
| JC, online | Accept |
| JC, onsite | Accept if the postal code is in a prime sector or within 45min by transit |
| Non-JC | Accept, unless the rate is "tutor to propose" |
| Non-JC | Accept if prime or within 45min by transit. "Propose" listings must be prime |

Prime sectors: Sentosa (09), D9-11 (22-30), East Coast (42-45), Upper Bukit Timah (58-59).

# Setup
**Requirements:** Python 3.10+, a Telegram account, and API keys for Telegram, Gemini and Google Maps.

```bash
git clone https://github.com/owenluozy/telegram-tutor-filtering-bot.git
cd telegram-tutor-filtering-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:
| Variable | Where to get it |
| --- | --- |
| `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | https://my.telegram.org -> API development tools |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `GMAPS_API_KEY` | Google Cloud Console (enable the Distance Matrix API) |
| `ORIGINS` | Semicolon-separated start points for the travel-time check |

## Run

```bash
python tutor_bot.py
```

On the first run, Telegram sends a login code to your account. A local `tutor_session.session` file is created so you stay logged in.

To see which Gemini models your key can use:

```bash
python check_models.py
```

## Customising

Edit the constants at the top of `tutor_bot.py`:
- `TARGET_CHANNELS`: channels to monitor
- `PRIME_SECTOR`: postal sectors that skip the travel-time check
- `AI_MODEL`: Gemini model used
- `MIN_RATE`: rate threshold
- `MAX_TRAVEL_SECONDS`: travel-time threshold in seconds
