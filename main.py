import os, httpx, asyncio
from datetime import datetime
from collections import deque
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI(title="WhatsApp AI Bot")
templates = Jinja2Templates(directory="templates")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "tharoor-secret-123")
RENDER_URL = os.getenv("RENDER_URL", "")

conversation_store: dict[str, list] = {}
mood_store: dict[str, list] = {}        # tracks mood history per chat
topic_store: dict[str, str] = {}        # tracks current topic per chat
gender_store: dict[str, str] = {}
recent_messages: deque = deque(maxlen=20)
bot_enabled = True

stats = {
    "total_replies": 0,
    "total_messages": 0,
    "started_at": datetime.now().isoformat(),
    "last_reply_at": None,
}

MALE_NAMES = [
    "rahul", "raj", "amit", "vikram", "suresh", "ramesh", "ganesh", "arjun",
    "rohit", "sanjay", "vijay", "ajay", "ravi", "arun", "nikhil", "deepak",
    "manish", "rakesh", "sachin", "virat", "hardik", "karan", "rohan", "aarav",
    "dev", "ishaan", "kabir", "krishna", "milan", "naveen", "om", "pranav",
    "siddharth", "tarun", "uday", "varun", "yash", "zubin", "harsh", "kunal",
    "mohit", "neeraj", "piyush", "sahil", "tushar", "ankit", "bhavesh", "pratik",
    "vishal", "sumit", "praveen", "manoj", "dinesh", "sunil", "aditya", "akash"
]

FEMALE_NAMES = [
    "priya", "pooja", "neha", "anjali", "kavya", "divya", "sneha", "anita",
    "sunita", "rekha", "meena", "sona", "rani", "maya", "nisha", "riya",
    "shreya", "swati", "tanvi", "usha", "vidya", "aisha", "bhavna", "charu",
    "deepa", "ekta", "falak", "gargi", "hema", "isha", "jyoti", "komal",
    "lata", "mansi", "namrata", "pallavi", "radha", "sapna", "trisha", "uma",
    "vandana", "yamini", "zoya", "simran", "gurpreet", "harpreet", "jasmine",
    "kirti", "lavanya", "meenal", "payal", "rashmi", "shweta", "tanu", "varsha"
]

FEMALE_WORDS = ["bestie", "girly", "queen", "hun", "babe", "cutie", "awwie", "hehe", "teehee"]
MALE_WORDS   = ["bhai", "bro", "dude", "boss", "bruh", "bhaiya"]


def detect_gender_from_name(name: str) -> str:
    n = name.lower().strip()
    for m in MALE_NAMES:
        if m in n: return "male"
    for f in FEMALE_NAMES:
        if f in n: return "female"
    return "unknown"


def detect_gender_from_message(message: str) -> str:
    ml = message.lower()
    fs = sum(1 for w in FEMALE_WORDS if w in ml)
    ms = sum(1 for w in MALE_WORDS if w in ml)
    if fs > ms: return "female"
    if ms > fs: return "male"
    return "unknown"


def get_gender(chat_id: str, name: str, message: str) -> str:
    if chat_id in gender_store and gender_store[chat_id] != "unknown":
        return gender_store[chat_id]
    gender = detect_gender_from_name(name)
    if gender == "unknown":
        gender = detect_gender_from_message(message)
    gender_store[chat_id] = gender
    return gender


def detect_mood(message: str) -> str:
    ml = message.lower()
    if any(w in ml for w in ["sad", "crying", "upset", "hurt", "miss", "lonely", "depressed", "low", "bad day", "heartbreak"]):
        return "sad"
    if any(w in ml for w in ["happy", "excited", "amazing", "love", "great", "awesome", "yay", "woohoo", "got the", "passed", "selected"]):
        return "happy"
    if any(w in ml for w in ["angry", "hate", "frustrat", "annoyed", "irritat", "mad", "pissed"]):
        return "angry"
    if any(w in ml for w in ["stress", "worried", "anxious", "nervous", "scared", "panic", "overwhelm", "pressure"]):
        return "stressed"
    if any(w in ml for w in ["tired", "exhausted", "sleepy", "drained", "burned out"]):
        return "tired"
    if any(w in ml for w in ["bored", "nothing to do", "boring", "free", "dull"]):
        return "bored"
    if any(w in ml for w in ["haha", "lol", "lmao", "funny", "joke", "😂", "😆"]):
        return "funny"
    return "neutral"


def get_mood_summary(chat_id: str) -> str:
    if chat_id not in mood_store or not mood_store[chat_id]:
        return "neutral"
    moods = mood_store[chat_id][-5:]  # last 5 moods
    # find most common mood
    mood_counts = {}
    for m in moods:
        mood_counts[m] = mood_counts.get(m, 0) + 1
    return max(mood_counts, key=mood_counts.get)


def build_prompt(gender: str, chat_id: str, sender_name: str) -> str:
    hour = datetime.now().hour

    if 5 <= hour < 12:
        time_of_day = "morning"
        time_reply = "Good morning! Hope you slept well 😊"
    elif 12 <= hour < 17:
        time_of_day = "afternoon"
        time_reply = "Good afternoon! Hope the day's going well 😊"
    elif 17 <= hour < 21:
        time_of_day = "evening"
        time_reply = "Good evening! How was your day? 😊"
    else:
        time_of_day = "night"
        time_reply = "Hey! Up so late? 😄"

    # Get mood trend for this person
    overall_mood = get_mood_summary(chat_id)
    current_topic = topic_store.get(chat_id, "none")

    # Gender tone
    if gender == "female":
        gender_style = """
TALKING TO: A girl/woman (as her male friend)
- Warm, caring, supportive tone
- Be like a close caring male friend
- Emojis: 😊 🥺 😄 ❤️ occasionally
"""
    elif gender == "male":
        gender_style = """
TALKING TO: A guy/man (as his male friend)
- Casual, chill, direct like a close male friend
- Emojis: 💪 😂 🔥 😎 occasionally
"""
    else:
        gender_style = """
TALKING TO: Someone (gender unknown)
- Friendly, warm, neutral tone
- Natural and easy going
"""

    return f"""You are replying on behalf of the owner of this WhatsApp account.
The owner is a MALE replying to personal WhatsApp messages.

CURRENT CONTEXT:
- Time of day: {time_of_day}
- Person's name: {sender_name}
- Their recent mood trend: {overall_mood}
- Current topic being discussed: {current_topic}
- If they greet with good morning/afternoon/evening/night → use: "{time_reply}"

{gender_style}

CONTEXT AWARENESS RULES:
- Read the last 10 messages carefully before replying
- If they were sad before and now seem okay → acknowledge the change naturally
- If they were discussing a topic → continue that topic naturally, dont restart
- If they asked a question before that wasnt answered → answer it now
- If mood changed from sad to happy → notice it warmly
- If mood changed from happy to sad → immediately be supportive
- Remember what was said earlier in conversation and refer to it naturally
- If they mentioned plans (meeting, call, trip) → ask about it naturally later

CASUAL WORDS RULE — VERY IMPORTANT:
- Do NOT use yaar, bhai, bro in every message
- Use these words ONLY during emotional moments:
  * When they are sad or upset
  * When celebrating something big
  * When being very supportive
  * Max once per emotional conversation
- In normal casual chat → just talk naturally without these words
- Sound like a real person, not a script

EMOTION RESPONSE GUIDE:
- Sad/upset → be caring, ask what happened, be present
- Happy/excited → match energy, celebrate with them
- Angry → stay calm, understand their side
- Stressed → be reassuring, offer perspective
- Tired → acknowledge it, be gentle
- Bored → be fun, suggest something or joke around
- Funny/joking → laugh along naturally
- Neutral/casual → just be normal and conversational

STRICT RULES:
- Max 2-3 sentences per reply
- Simple plain English always
- Sound like typing on phone — natural and quick
- Never reveal you are AI or bot
- No big words or formal language
- No unnecessary filler words
- Be genuinely conversational — not robotic
- Reply should feel like it came from a real person
"""


@app.on_event("startup")
async def start_keepalive():
    if RENDER_URL:
        asyncio.create_task(keepalive_loop())


async def keepalive_loop():
    await asyncio.sleep(30)
    async with httpx.AsyncClient() as http:
        while True:
            try:
                await http.get(f"{RENDER_URL}/health", timeout=10)
                print("🏓 Keepalive ping sent")
            except Exception as e:
                print(f"Keepalive error: {e}")
            await asyncio.sleep(600)


@app.get("/health")
def health():
    return {"status": "ok", "bot_enabled": bot_enabled}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "bot_enabled": bot_enabled,
        "recent_messages": list(recent_messages),
    })


@app.get("/api/stats")
def api_stats():
    return {
        **stats,
        "bot_enabled": bot_enabled,
        "active_chats": len(conversation_store),
        "gender_store": gender_store,
        "mood_store": {k: v[-3:] for k, v in mood_store.items()},
        "topic_store": topic_store,
        "recent_messages": list(recent_messages)[-10:],
    }


@app.post("/reply")
async def generate_reply(request: Request):
    if not bot_enabled:
        return JSONResponse({"reply": None, "reason": "bot_disabled"})

    data = await request.json()
    chat_id   = data.get("chat_id", "default")
    sender_name = data.get("sender_name", "Friend")
    message   = data.get("message", "")

    if not message.strip():
        return JSONResponse({"reply": None})

    stats["total_messages"] += 1

    # Detect gender
    gender = get_gender(chat_id, sender_name, message)

    # Detect and store mood
    current_mood = detect_mood(message)
    if chat_id not in mood_store:
        mood_store[chat_id] = []
    mood_store[chat_id].append(current_mood)
    if len(mood_store[chat_id]) > 20:
        mood_store[chat_id] = mood_store[chat_id][-20:]

    # Build conversation history — last 10 messages
    if chat_id not in conversation_store:
        conversation_store[chat_id] = []

    history = conversation_store[chat_id]
    history.append({"role": "user", "content": f"[{sender_name}]: {message}"})
    if len(history) > 10:
        conversation_store[chat_id] = history[-10:]
        history = conversation_store[chat_id]

    print(f"📨 {sender_name} | gender: {gender} | mood: {current_mood}")

    try:
        # System prompt with full context
        system_prompt = build_prompt(gender, chat_id, sender_name)

        # Pass full conversation history to AI
        messages = [{"role": "system", "content": system_prompt}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=150,
            temperature=0.82
        )
        reply = response.choices[0].message.content.strip()

        # Extract topic from reply for context tracking
        # Simple topic detection — store last meaningful topic
        topic_keywords = {
            "work": ["work", "office", "job", "meeting", "boss", "project", "deadline"],
            "food": ["food", "eat", "lunch", "dinner", "hungry", "restaurant"],
            "travel": ["trip", "travel", "going to", "visit", "flight", "train"],
            "health": ["sick", "health", "doctor", "hospital", "medicine", "fever"],
            "relationship": ["friend", "family", "mom", "dad", "sister", "brother", "boyfriend", "girlfriend"],
            "studies": ["exam", "study", "college", "marks", "result", "class"],
        }
        msg_lower = message.lower()
        for topic, keywords in topic_keywords.items():
            if any(k in msg_lower for k in keywords):
                topic_store[chat_id] = topic
                break

    except Exception as e:
        print(f"❌ Groq Error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "type": type(e).__name__}
        )

    history.append({"role": "assistant", "content": reply})
    stats["total_replies"] += 1
    stats["last_reply_at"] = datetime.now().isoformat()

    recent_messages.appendleft({
        "sender": sender_name,
        "gender": gender,
        "mood": current_mood,
        "topic": topic_store.get(chat_id, "general"),
        "message": message[:80] + ("..." if len(message) > 80 else ""),
        "reply": reply[:120] + ("..." if len(reply) > 120 else ""),
        "time": datetime.now().strftime("%H:%M:%S"),
        "chat_id": chat_id,
    })

    return JSONResponse({
        "reply": reply,
        "gender_detected": gender,
        "mood_detected": current_mood,
        "topic": topic_store.get(chat_id, "general")
    })


def verify_secret(secret: str):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")


@app.post("/webhook/enable")
async def webhook_enable(request: Request, x_webhook_secret: str = Header(...)):
    verify_secret(x_webhook_secret)
    global bot_enabled
    bot_enabled = True
    return {"status": "bot enabled", "bot_enabled": True}


@app.post("/webhook/disable")
async def webhook_disable(request: Request, x_webhook_secret: str = Header(...)):
    verify_secret(x_webhook_secret)
    global bot_enabled
    bot_enabled = False
    return {"status": "bot disabled", "bot_enabled": False}


@app.post("/webhook/clear-history")
async def webhook_clear(request: Request, x_webhook_secret: str = Header(...)):
    verify_secret(x_webhook_secret)
    data = await request.json()
    chat_id = data.get("chat_id")
    if chat_id:
        conversation_store.pop(chat_id, None)
        gender_store.pop(chat_id, None)
        mood_store.pop(chat_id, None)
        topic_store.pop(chat_id, None)
        return {"cleared": chat_id}
    conversation_store.clear()
    gender_store.clear()
    mood_store.clear()
    topic_store.clear()
    return {"cleared": "all"}


@app.post("/webhook/set-gender")
async def webhook_set_gender(request: Request, x_webhook_secret: str = Header(...)):
    verify_secret(x_webhook_secret)
    data = await request.json()
    chat_id = data.get("chat_id")
    gender = data.get("gender")
    if not chat_id or gender not in ["male", "female", "unknown"]:
        raise HTTPException(status_code=400, detail="chat_id and gender required")
    gender_store[chat_id] = gender
    return {"chat_id": chat_id, "gender_set": gender}
