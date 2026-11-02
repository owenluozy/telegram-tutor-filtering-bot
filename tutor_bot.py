import os
import json
import asyncio
import googlemaps
from dotenv import load_dotenv
from telethon import TelegramClient, events
from google import genai
from google.genai import types
from datetime import datetime, timedelta
from functools import lru_cache

# --- 1. CREDENTIALS (loaded from .env, see .env.example) ---
load_dotenv()
TELEGRAM_API_ID = int(os.environ["TELEGRAM_API_ID"])
TELEGRAM_API_HASH = os.environ["TELEGRAM_API_HASH"]
GMAPS_API_KEY = os.environ["GMAPS_API_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
ORIGINS = [o.strip() for o in os.environ["ORIGINS"].split(";")]

TARGET_CHANNELS = ['TutorSociety']

AI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
MIN_RATE = 60
MAX_TRAVEL_SECONDS = 45 * 60

# --- 2. PRIME ESTATE POSTAL SECTORS ---
# D9/10/11 (22-30), East Coast (42-45), Upper Bt Timah (58-59), Sentosa (09)
PRIME_SECTORS = [
    "09", "22", "23", "24", "25", "26", "27", "28", "29", "30", 
    "42", "43", "44", "45", "58", "59"
]

# Initialize Clients
client = TelegramClient('tutor_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)
gmaps = googlemaps.Client(key=GMAPS_API_KEY)
ai = genai.Client(api_key=GEMINI_API_KEY)

# Process listings one-by-one
gemini_lock = asyncio.Lock()


def parse_listing_with_ai(message_text):
    """Uses Gemini to turn the messy Telegram text into clean JSON variables"""
    prompt = f"""
    Analyze this tuition assignment and return ONLY a JSON object.
    Rules:
    - subject_is_valid: true ONLY if the subject involves Math, Biology, Chemistry, or Science.
    - is_jc: true ONLY if it involves JC1, JC2, H1, or H2.
    - is_online: true if location says online or zoom.
    - rate_type: "fixed", "range", or "propose". 
    - max_rate_per_hour: The highest hourly rate mentioned (number only). If "tutor to propose", return null.
    - postal_code: Extract the 6-digit Singapore postal code. If none, return null.
    
    Listing:
    {message_text}
    """
    
    response = ai.models.generate_content(
        model=AI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        return {}

def next_weekday_5pm():
    d = datetime.now() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.replace(hour=17, minute=0, second=0, microsecond=0)

@lru_cache(maxsize=512)
def _travel_time_ok(postal_code):
    """ Real Maps call. Errors are raised, so theya re never cached."""
    destination = f"Singapore {postal_code}"
    matrix = gmaps.distance_matrix(
        origins= ORIGINS,
        destinations = [destination],
        mode="transit",
        departure_time=next_weekday_5pm()
    )
    for row in matrix['rows']:
        element = row['elements'][0]
        if element.get('status') == 'OK':
            duration_seconds = element['duration']['value']
            if duration_seconds <= MAX_TRAVEL_SECONDS:
                return True
    return False

def check_travel_time(postal_code):
    """Checks if public transit is within MAX_TRAVEL_SECONDS of any origin."""
    if not postal_code:
        return False
    try:
        return _travel_time_ok(postal_code)
    except Exception as e:
        print(f"Maps API Error: {e}")
        return False
    destination = f"Singapore {postal_code}"



def meets_your_criteria(data):
    """Your exact 6 rules converted into Python logic"""
    if not data.get("subject_is_valid"):
        return False

    rate_type = data.get("rate_type")
    try:
        max_rate = float(data.get("max_rate_per_hour") or 0)
    except (TypeError, ValueError):
        max_rate = 0
    
    if rate_type != "propose":
        if not max_rate or max_rate < MIN_RATE:
            return False

    is_jc = data.get("is_jc")
    is_online = data.get("is_online")
    postal = data.get("postal_code")
    
    def is_prime(postal_code):
        if not postal_code: return False
        return str(postal_code)[:2] in PRIME_SECTORS

    if is_jc:
        if is_online:
            return True 
        else:
            if not postal: return False
            return is_prime(postal) or check_travel_time(postal)

    else: 
        if is_online:
            if rate_type == "propose":
                return False
            return True 
        else:
            if not postal: return False
            if rate_type == "propose":
                return is_prime(postal)
            else:
                return is_prime(postal) or check_travel_time(postal)


@client.on(events.NewMessage(chats=TARGET_CHANNELS))
async def handle_new_assignment(event):
    message_text = event.raw_text
    if not message_text:
        return

    try:
        async with gemini_lock:
            await asyncio.sleep(10)
            
            structured_data = await asyncio.to_thread(parse_listing_with_ai, message_text)
        
        is_match = await asyncio.to_thread(meets_your_criteria, structured_data)
        
        if is_match:
            alert = "🎯 **PERFECT MATCH FOUND!**\n\n" + message_text
            await client.send_message('me', alert)
            print("Match found and forwarded!")
            
    except Exception as e:
        print(f"Error processing message: {e}")


async def main():
    await client.start()
    print("🤖 Advanced AI Tutor Bot is running... (v2 with Queueing)")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())

