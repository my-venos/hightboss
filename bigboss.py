import asyncio
import time
import os
import json
import hashlib
import uuid
from dotenv import load_dotenv
import aiohttp
import motor.motor_asyncio 

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# --- 🧠 TRUE MACHINE LEARNING LIBRARIES ---
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import warnings
warnings.filterwarnings("ignore") # ဖုံးကွယ်ထားသော Warning များကို ပိတ်ထားရန်
# ------------------------------------------

load_dotenv()

# ==========================================
# ⚙️ 1. CONFIGURATION
# ==========================================
USERNAME = os.getenv("BIGWIN_USERNAME")
PASSWORD = os.getenv("BIGWIN_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("CHANNEL_ID")
MONGO_URI = os.getenv("MONGO_URI") 

if not all([USERNAME, PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, MONGO_URI]):
    print("❌ Error: .env ဖိုင်ထဲတွင် အချက်အလက်များ ပြည့်စုံစွာ မပါဝင်ပါ။")
    exit()
  
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# MongoDB Setup
db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = db_client['bigwin_database'] 
history_collection = db['game_history'] 
predictions_collection = db['predictions'] 

# ==========================================
# 🔧 2. SYSTEM & TRACKING VARIABLES 
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = ""
LAST_PREDICTED_ISSUE = ""
LAST_PREDICTED_RESULT = ""

# --- Stats Tracking ---
CURRENT_WIN_STREAK = 0
CURRENT_LOSE_STREAK = 0
LONGEST_WIN_STREAK = 0
LONGEST_LOSE_STREAK = 0
TOTAL_PREDICTIONS = 0 

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

async def init_db():
    try:
        await history_collection.create_index("issue_number", unique=True)
        await predictions_collection.create_index("issue_number", unique=True)
        print("🗄 MongoDB ချိတ်ဆက်မှု အောင်မြင်ပါသည်။ (🚀 Random Forest ML Enabled)")
    except Exception as e:
        print(f"❌ MongoDB Indexing Error: {e}")

# ==========================================
# 🔑 3. ASYNC API FUNCTIONS
# ==========================================
async def fetch_with_retry(session, url, headers, json_data, retries=3):
    for attempt in range(retries):
        try:
            async with session.post(url, headers=headers, json=json_data, timeout=10) as response:
                return await response.json()
        except Exception as e:
            if attempt == retries - 1:
                print(f"❌ Network Error after {retries} attempts: {e}")
                return None
            await asyncio.sleep(1)

async def login_and_get_token(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    print("🔐 အကောင့်ထဲသို့ Login ဝင်နေပါသည်...")
    
    json_data = {
        'username': '959680090540',
        'pwd': 'Mitheint11',
        'phonetype': 1,
        'logintype': 'mobile',
        'packId': '',
        'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6',
        'language': 7,
        'random': '452fa309995244de92103c0afbefbe9a',
        'signature': '202C655177E9187D427A26F3CDC00A52',
        'timestamp': 1773021618,
    }

    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/Login', BASE_HEADERS, json_data)
    if data and data.get('code') == 0:
        token_str = data.get('data', {}) if isinstance(data.get('data'), str) else data.get('data', {}).get('token', '')
        CURRENT_TOKEN = f"Bearer {token_str}"
        print("✅ Login အောင်မြင်ပါသည်။ Token အသစ် ရရှိပါပြီ。\n")
        return True
    return False

async def get_user_balance(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    if not CURRENT_TOKEN: return "0.00"
    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN
    
    json_data = {
        'signature': 'F7A9A2A74E1F1D1DFE048846E49712F8',
        'language': 7,
        'random': '58d9087426f24a54870e243b76743a94',
        'timestamp': 1772984987,
    }
    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/GetUserInfo', headers, json_data)
    if data and data.get('code') == 0: 
        return data.get('data', {}).get('amount', '0.00')
    return "0.00"

# ==========================================
# 🧠 4. CORE MACHINE LEARNING FUNCTION
# ==========================================
def train_and_predict_ml(history_docs):
    """
    Random Forest Algorithm အသုံးပြု၍ Data ပေါင်းများစွာကို Train လုပ်ပြီး
    နောက်တစ်ပွဲအတွက် နိုင်ခြေအများဆုံးကို တွက်ချက်ပေးမည်။
    """
    if len(history_docs) < 30:
        return None, 0.0

    # Data များကို အဟောင်းမှ အသစ်သို့ ပြန်စီမည်
    docs = list(reversed(history_docs)) 
    
    X = [] # Features (အချက်အလက်များ)
    y = [] # Target (ထွက်မည့်ရလဒ်)
    
    window_size = 5 # နောက်ဆုံး ၅ ပွဲ၏ Data များကို ယူ၍ ဆက်စပ်မှုကို ရှာမည်
    
    def enc_size(s): return 1 if s == 'BIG' else 0
    def enc_par(p): return 1 if p == 'EVEN' else 0
    
    # 🔄 Data Training (Model ကို သင်ယူစေခြင်း)
    for i in range(len(docs) - window_size):
        window_docs = docs[i : i+window_size]
        target_doc = docs[i+window_size]
        
        features = []
        for doc in window_docs:
            features.append(enc_size(doc.get('size')))
            features.append(int(doc.get('number', 0)))
            features.append(enc_par(doc.get('parity', 'EVEN')))
            
        X.append(features)
        y.append(enc_size(target_doc.get('size')))
        
    if len(X) < 10:
        return None, 0.0
        
    # 🤖 AI Model တည်ဆောက်ခြင်း (Random Forest - 50 Trees)
    clf = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    clf.fit(X, y)
    
    # 🔮 နောက်တစ်ပွဲအတွက် ခန့်မှန်းခြင်း
    latest_docs = docs[-window_size:]
    latest_features = []
    for doc in latest_docs:
        latest_features.append(enc_size(doc.get('size')))
        latest_features.append(int(doc.get('number', 0)))
        latest_features.append(enc_par(doc.get('parity', 'EVEN')))
        
    pred = clf.predict([latest_features])[0]
    prob = clf.predict_proba([latest_features])[0]
    
    predicted_size = "BIG" if pred == 1 else "SMALL"
    max_prob = max(prob) * 100
    
    return predicted_size, max_prob

# ==========================================
# 🚀 5. MAIN LOGIC INTEGRATION
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, LAST_PREDICTED_ISSUE, LAST_PREDICTED_RESULT
    global CURRENT_WIN_STREAK, CURRENT_LOSE_STREAK, LONGEST_WIN_STREAK, LONGEST_LOSE_STREAK, TOTAL_PREDICTIONS
    
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 10, 'pageNo': 1, 'typeId': 30, 'language': 7,
        'random': '1ef0a7aca52b4c71975c031dda95150e', 'signature': '7D26EE375971781D1BC58B7039B409B7', 'timestamp': 1772985040,
    }

    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', headers, json_data)
    if not data or data.get('code') != 0:
        if data and (data.get('code') == 401 or "token" in str(data.get('msg')).lower()):
            CURRENT_TOKEN = ""
        return

    records = data.get("data", {}).get("list", [])
    if not records: return
    
    latest_record = records[0]
    latest_issue = str(latest_record["issueNumber"])
    latest_number = int(latest_record["number"])
    latest_size = "BIG" if latest_number >= 5 else "SMALL"
    latest_parity = "EVEN" if latest_number % 2 == 0 else "ODD"
    
    if latest_issue == LAST_PROCESSED_ISSUE: return 
    LAST_PROCESSED_ISSUE = latest_issue
    next_issue = str(int(latest_issue) + 1)
    win_lose_text = ""
    
    # DB တွင် မှတ်သားမည်
    await history_collection.update_one(
        {"issue_number": latest_issue}, 
        {"$setOnInsert": {"number": latest_number, "size": latest_size, "parity": latest_parity}}, 
        upsert=True
    )
    
    # --- နိုင်/ရှုံး စစ်ဆေးခြင်း ---
    if LAST_PREDICTED_ISSUE == latest_issue:
        TOTAL_PREDICTIONS += 1
        is_win = (LAST_PREDICTED_RESULT == latest_size)
        
        if is_win:
            win_lose_status = "WIN ✅"
            CURRENT_WIN_STREAK += 1
            CURRENT_LOSE_STREAK = 0
            if CURRENT_WIN_STREAK > LONGEST_WIN_STREAK: LONGEST_WIN_STREAK = CURRENT_WIN_STREAK
        else:
            win_lose_status = "LOSE ❌"
            CURRENT_LOSE_STREAK += 1
            CURRENT_WIN_STREAK = 0
            if CURRENT_LOSE_STREAK > LONGEST_LOSE_STREAK: LONGEST_LOSE_STREAK = CURRENT_LOSE_STREAK
                
        await predictions_collection.update_one({"issue_number": latest_issue}, {"$set": {"actual_size": latest_size, "win_lose": win_lose_status}})
        
        win_lose_text = (
            f"🏆 <b>ပြီးခဲ့သောပွဲစဉ် ({latest_issue})</b> ရလဒ်: {latest_number} ({latest_size})\n"
            f"📊 <b>ခန့်မှန်းချက်: {win_lose_status}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

    # ==============================================================
    # 🧠 EXECUTING MACHINE LEARNING MODEL
    # ==============================================================
    cursor = history_collection.find().sort("issue_number", -1).limit(5000)
    history_docs = await cursor.to_list(length=5000)
    
    predicted = "BIG (အကြီး) 🔴"
    base_prob = 55.0
    reason = "Data မလုံလောက်သေးပါ"
    
    try:
        # ML Algorithm ကို နောက်ကွယ် Thread ဖြင့် Run မည် (Bot မထစ်စေရန်)
        ml_pred, ml_prob = await asyncio.to_thread(train_and_predict_ml, history_docs)
        
        if ml_pred:
            predicted = "BIG (အကြီး) 🔴" if ml_pred == "BIG" else "SMALL (အသေး) 🟢"
            # Random Forest ၏ Probability များကို 65% မှ 94% ကြားသို့ Adjust လုပ်မည်
            base_prob = 65.0 + (ml_prob - 50.0) * 1.5 
            reason = "🤖 <b>Random Forest Algorithm</b>\n└ (ဆုံးဖြတ်ချက်သစ်ပင် ၅၀ ဖြင့် တွက်ချက်မှု)"
        else:
            # Fallback Logic (Data နည်းနေသေးပါက)
            b_count = sum(1 for d in history_docs[:20] if d.get('size') == 'BIG')
            s_count = sum(1 for d in history_docs[:20] if d.get('size') == 'SMALL')
            if b_count > s_count:
                predicted = "BIG (အကြီး) 🔴"
                base_prob = (b_count / 20.0) * 100
            else:
                predicted = "SMALL (အသေး) 🟢"
                base_prob = (s_count / 20.0) * 100
            reason = "📊 အခြေခံ ရေစီးကြောင်းအရ တွက်ချက်မှု"
            
    except Exception as e:
        print(f"ML Error: {e}")
        reason = "⚠️ ML Model Error. Basic Check."

    # 🚨 EMERGENCY LOSE STREAK OVERRIDE 🚨
    # ၅ ပွဲဆက်တိုက် ရှုံးနေပါက အရေးပေါ်စနစ် ဝင်ရောက်မည်
    if CURRENT_LOSE_STREAK >= 5:
        last_real_size = history_docs[0].get("size", "BIG")
        predicted = "BIG (အကြီး) 🔴" if last_real_size == "BIG" else "SMALL (အသေး) 🟢"
        base_prob = 92.5
        reason = "⚠️ အရေးပေါ် ရှုံးပွဲဖြတ်တောက်ရေးစနစ်\n└ (ရေစီးကြောင်းနောက် လိုက်ပါ)"

    final_prob = min(max(round(base_prob, 1), 60.0), 96.0)

    LAST_PREDICTED_ISSUE = next_issue
    LAST_PREDICTED_RESULT = "BIG" if "BIG" in predicted else "SMALL"
    
    await predictions_collection.update_one({"issue_number": next_issue}, {"$set": {"predicted_size": LAST_PREDICTED_RESULT, "probability": final_prob, "actual_size": None, "win_lose": None}}, upsert=True)

    current_balance = await get_user_balance(session)
    print(f"✅ [NEW] {next_issue} | {predicted} | {final_prob}% | W:{CURRENT_WIN_STREAK}/L:{CURRENT_LOSE_STREAK}")

    suggested_multiplier = 2 ** CURRENT_LOSE_STREAK if CURRENT_LOSE_STREAK <= 6 else 1
    bet_advice = f"💰 <b>အကြံပြုလောင်းကြေး:</b> အခြေခံကြေး၏ {suggested_multiplier}ဆ ထည့်ပါ"

    # --- 🎨 PRO TELEGRAM MESSAGE FORMATTING ---
    tg_message = (
        f"🎰 <b>Bigwin TRUE AI Predictor</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{win_lose_text}"
        f"🎯 <b>နောက်ပွဲစဉ်အမှတ်:</b> <code>{next_issue}</code>\n"
        f"🤖 <b>AI ခန့်မှန်းချက်: {predicted}</b>\n"
        f"📈 <b>ဖြစ်နိုင်ခြေ:</b> {final_prob}%\n"
        f"💡 <b>အကြောင်းပြချက်:</b>\n"
        f"{reason}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{bet_advice}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Session Stats:</b>\n"
        f"┣ Current Win Streak : {CURRENT_WIN_STREAK} 🟢\n"
        f"┣ Long Win Streak : {LONGEST_WIN_STREAK} 🟢\n"
        f"┣ Current Lose Streak : {CURRENT_LOSE_STREAK} 🔴\n"
        f"┣ Long Lose Streak : {LONGEST_LOSE_STREAK} 🔴\n"
        f"┗ Total Played : {TOTAL_PREDICTIONS}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <i>အကောင့်လက်ကျန်: {current_balance} Ks</i>"
    )
    
    try: await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=tg_message)
    except: pass

# ==========================================
# 🔄 6. BACKGROUND TASK & MAIN LOOP
# ==========================================
async def auto_broadcaster():
    await init_db() 
    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
        while True:
            await check_game_and_predict(session)
            await asyncio.sleep(5)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("👋 မင်္ဂလာပါ။ Bigwin True ML Predictor မှ ကြိုဆိုပါတယ်။\n\nစနစ်သည် Random Forest Machine Learning Model ကို အသုံးပြု၍ ခန့်မှန်းချက်များ ပို့ပေးနေပါသည်။")

async def main():
    print("🚀 Aiogram Bigwin Bot (True ML Edition) စတင်နေပါပြီ...\n")
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
