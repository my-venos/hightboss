import asyncio
import time
import os
from dotenv import load_dotenv
import aiohttp

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

load_dotenv()

# ==========================================
# ⚙️ 1. CONFIGURATION (ပြင်ဆင်ရန် အပိုင်း)
# ==========================================
USERNAME = os.getenv("BIGWIN_USERNAME")
PASSWORD = os.getenv("BIGWIN_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("CHANNEL_ID")

# Data များ မှန်ကန်စွာ ပါဝင်ခြင်း ရှိမရှိ စစ်ဆေးခြင်း
if not all([USERNAME, PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
    print("❌ Error: .env ဖိုင်ထဲတွင် အချက်အလက်များ ပြည့်စုံစွာ မပါဝင်ပါ။")
    exit()
  
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ==========================================
# 🔧 2. SYSTEM & AUTO-BET VARIABLES
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = ""

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

# 🤖 Auto-Bet Settings
AUTO_BET_ENABLED = False
MULTIPLIERS = [1, 2, 5, 10, 22] # ရှုံးလျှင် ဆတိုးမည့် အဆင့်များ
BASE_BET = 10                   # အခြေခံ လောင်းကြေး (၁ ဆ)
CURRENT_STEP = 0

LAST_BET_ISSUE = ""
LAST_BET_CHOICE = "" 
LAST_BET_AMOUNT = 0

# 📈 AI Win Rate Tracking
LAST_AI_ISSUE = ""
LAST_AI_CHOICE = ""
WIN_HISTORY = [] # AI ခန့်မှန်းချက် မှန်/မမှန် မှတ်သားရန် (1=Win, 0=Loss)

# ==========================================
# 🔑 3. ASYNC API FUNCTIONS
# ==========================================
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
    'random': '026e324cf3d14440b8c261ad356610a6',
    'signature': '842781239D9D89DCEF83A2E5480C7890',
    'timestamp': 1772963120,
}

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/Login', headers=BASE_HEADERS, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0:
                token_data = data.get('data', {})
                token_str = token_data if isinstance(token_data, str) else token_data.get('token', '')
                CURRENT_TOKEN = f"Bearer {token_str}"
                print("✅ Login အောင်မြင်ပါသည်။ Token အသစ် ရရှိပါပြီ。\n")
                return True
            else:
                print(f"❌ Login Failed: {data.get('msg')}")
                return False
    except Exception as e:
        print(f"❌ Login Request Error: {e}")
        return False

async def get_user_balance(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return "0.00"

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'signature': '98BA4B555CD283B47C8F9F6C800DF741',
        'language': 7,
        'random': 'd36e1e8dadca4bdd8d5f2e08f1b06c56',
        'timestamp': 1772963120, # Signature Error မဖြစ်စေရန် Static ထားသည်
    }

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GetUserInfo', headers=headers, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0:
                return data.get('data', {}).get('amount', '0.00')
            elif data.get('code') == 401 or "token" in str(data.get('msg')).lower():
                CURRENT_TOKEN = ""
                return await get_user_balance(session) # Token သက်တမ်းကုန်လျှင် ပြန်ယူမည်
            return "0.00"
    except Exception:
        return "0.00"

async def place_bet(session: aiohttp.ClientSession, issue: str, choice: str, total_amount: int):
    global CURRENT_TOKEN
    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN
    
    # BIG ဆိုလျှင် 14, SMALL ဆိုလျှင် 15 (ဂိမ်းပေါ်မူတည်၍ လိုအပ်ပါက ပြင်ပါ)
    select_id = 14 if choice == "BIG" else 15 
    bet_count = total_amount // 10
    
    json_data = {
        'typeId': 30,
        'issuenumber': issue,
        'amount': 10,               
        'betCount': bet_count,      
        'gameType': 2,
        'selectType': select_id,
        'language': 7,
        'random': 'efbf9e069bbf49119c4a4bf43ce15be6', 
        'signature': 'DFF30F1B1BAAE6512A07B1E0F5CF6A86',
        'timestamp': 1772966960, # Signature Error မဖြစ်စေရန် Static ထားသည်
    }
    
    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GameBetting', headers=headers, json=json_data) as response:
            data = await response.json()
            if data.get('code') == 0:
                print(f"💸 [BET SUCCESS] ပွဲစဉ် {issue} တွင် {choice} ကို {total_amount} Ks လောင်းလိုက်ပါပြီ။")
                return True
            else:
                print(f"❌ [BET FAILED] ပွဲစဉ် {issue} လောင်းရန်မအောင်မြင်ပါ: {data.get('msg')}")
                return False
    except Exception as e:
        print(f"❌ [BET ERROR] Request Error: {e}")
        return False

async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, CURRENT_STEP, LAST_BET_ISSUE, LAST_BET_CHOICE, LAST_BET_AMOUNT
    global LAST_AI_ISSUE, LAST_AI_CHOICE, WIN_HISTORY
    
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 30, # AI တွက်ချက်မှု ပိုမိုတိကျစေရန် 30 သို့ထားပါသည်
        'pageNo': 1,
        'typeId': 30,
        'language': 7,
        'random': '85b82082418845c593a2641ae50af6de',
        'signature': 'E7C0AAF6D1B429E89F83CA6FDBF3D4FC',
        'timestamp': 1772962173, # Signature Error မဖြစ်စေရန် Static ထားသည်
    }

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', headers=headers, json=json_data) as response:
            data = await response.json()
            
            if data.get('code') == 0:
                records = data.get("data", {}).get("list", [])
                if not records: return
                
                latest_issue = str(records[0]["issueNumber"])
                
                if latest_issue == LAST_PROCESSED_ISSUE:
                    return # ပွဲစဉ်အသစ် မဟုတ်သေးပါက ကျော်သွားမည်
                    
                LAST_PROCESSED_ISSUE = latest_issue
                latest_num = int(records[0]["number"])
                next_issue = str(int(latest_issue) + 1)
                actual_result = "BIG" if latest_num >= 5 else "SMALL"
                
                # ---------------------------------------------
                # 📈 1. AI Win Rate (ရာခိုင်နှုန်း) တွက်ချက်ခြင်း
                # ---------------------------------------------
                if LAST_AI_ISSUE == latest_issue:
                    if actual_result == LAST_AI_CHOICE:
                        WIN_HISTORY.append(1) # မှန်လျှင် 1
                    else:
                        WIN_HISTORY.append(0) # မှားလျှင် 0
                        
                    # နောက်ဆုံးပွဲ ၂၀ စာသာ မှတ်မည်
                    if len(WIN_HISTORY) > 20:
                        WIN_HISTORY.pop(0)

                win_rate_msg = ""
                if len(WIN_HISTORY) > 0:
                    total_played = len(WIN_HISTORY)
                    total_won = sum(WIN_HISTORY)
                    total_lost = total_played - total_won
                    win_percentage = (total_won / total_played) * 100
                    win_rate_msg = f"📈 <b>Win Rate (Last {total_played}):</b> <code>{win_percentage:.0f}%</code> ({total_won}W - {total_lost}L)\n"
                else:
                    win_rate_msg = f"📈 <b>Win Rate:</b> <code>တွက်ချက်နေဆဲ...</code>\n"

                # ---------------------------------------------
                # 🏆 2. Auto-Bet လောင်းခဲ့လျှင် နိုင်/ရှုံး စစ်ဆေးခြင်း
                # ---------------------------------------------
                bet_result_msg = ""
                if AUTO_BET_ENABLED and LAST_BET_ISSUE == latest_issue:
                    if actual_result == LAST_BET_CHOICE:
                        CURRENT_STEP = 0
                        bet_result_msg = f"🎉 <b>လောင်းကြေးရလဒ်:</b> အရင်ပွဲ နိုင်ပါသည်! အစ (10Ks) မှ ပြန်စပါမည်။\n"
                    else:
                        CURRENT_STEP += 1
                        if CURRENT_STEP >= len(MULTIPLIERS):
                            CURRENT_STEP = 0 
                            bet_result_msg = f"💔 <b>လောင်းကြေးရလဒ်:</b> အမြင့်ဆုံးအဆင့်အထိ ရှုံးသွားသဖြင့် အစမှ ပြန်စပါမည်။\n"
                        else:
                            bet_result_msg = f"📉 <b>လောင်းကြေးရလဒ်:</b> ရှုံးပါသည်။ နောက်တစ်ဆင့် ({MULTIPLIERS[CURRENT_STEP]}ဆ) သို့ တက်ပါမည်။\n"

                # ---------------------------------------------
                # 🧠 3. ADVANCED AI PREDICTION (အဆင့်မြင့် တွက်ချက်မှု)
                # ---------------------------------------------
                history = ["B" if int(item["number"]) >= 5 else "S" for item in records]
                latest_result = history[0]

                current_streak = 1
                for i in range(1, len(history)):
                    if history[i] == latest_result: current_streak += 1
                    else: break

                is_ping_pong = False
                if len(history) >= 4:
                    if history[0] != history[1] and history[1] != history[2] and history[2] != history[3]:
                        is_ping_pong = True

                ai_raw_choice = ""
                reason = ""

                if current_streak >= 3:
                    ai_raw_choice = "BIG" if latest_result == "B" else "SMALL"
                    reason = f"လမ်းကြောင်းအားကောင်းနေသဖြင့် ({current_streak} ကြိမ်ဆက်) ပုံစံအတိုင်း လိုက်ပါမည်"
                elif is_ping_pong:
                    ai_raw_choice = "BIG" if latest_result == "S" else "SMALL"
                    reason = "ဘယ်ညာ (Ping-Pong) ပုံစံထွက်နေသဖြင့် ပြောင်းလဲလောင်းပါမည်"
                else:
                    follows_same = sum(1 for i in range(len(history) - 1) if history[i+1] == latest_result and history[i] == latest_result)
                    follows_diff = sum(1 for i in range(len(history) - 1) if history[i+1] == latest_result and history[i] != latest_result)

                    if follows_same > follows_diff:
                        ai_raw_choice = "BIG" if latest_result == "B" else "SMALL"
                        reason = "သမိုင်းကြောင်းအရ ထပ်တူထွက်လေ့ရှိသဖြင့် အဟောင်းအတိုင်း လိုက်ပါမည်"
                    elif follows_diff > follows_same:
                        ai_raw_choice = "BIG" if latest_result == "S" else "SMALL"
                        reason = "သမိုင်းကြောင်းအရ ပြောင်းထွက်လေ့ရှိသဖြင့် ဆန့်ကျင်ဘက်သို့ လောင်းပါမည်"
                    else:
                        b_count, s_count = history.count("B"), history.count("S")
                        ai_raw_choice = "BIG" if s_count > b_count else "SMALL"
                        reason = "Probability အရ ထွက်ရန်ကျန်နေသေးသော ဘက်သို့ လောင်းပါမည်"

                display_predict = "BIG (အကြီး) 🔴" if ai_raw_choice == "BIG" else "SMALL (အသေး) 🟢"

                LAST_AI_ISSUE = next_issue
                LAST_AI_CHOICE = ai_raw_choice

                # ---------------------------------------------
                # 💸 4. Auto-Bet လောင်းကြေးထပ်ခြင်း
                # ---------------------------------------------
                bet_info_msg = ""
                if AUTO_BET_ENABLED:
                    amount = BASE_BET * MULTIPLIERS[CURRENT_STEP]
                    await place_bet(session, next_issue, ai_raw_choice, amount) 
                    
                    LAST_BET_ISSUE = next_issue
                    LAST_BET_CHOICE = ai_raw_choice
                    LAST_BET_AMOUNT = amount
                    bet_info_msg = f"⚙️ <b>Auto-Bet :</b> <code>{amount} Ks</code> လောင်းထားပါသည်။\n"
                
                current_balance = await get_user_balance(session)
                
                # ---------------------------------------------
                # 💬 5. Telegram သို့ စာပို့ခြင်း
                # ---------------------------------------------
                print(f"✅ [NEW] ပွဲစဉ်: {latest_issue} -> 🤖 AI Predict: {display_predict}")

                tg_message = (
                    f"🎰 <b>Bigwin 30s | Pro-AI</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 <b>နောက်ပွဲစဉ်အမှတ် :</b> <code>{next_issue}</code>\n"
                    f"🤖 <b>AI ခန့်မှန်းချက် :</b> <b>{display_predict}</b>\n"
                    f"💡 <b>အကြောင်းပြချက် :</b> {reason}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"{win_rate_msg}"
                    f"{bet_result_msg}"
                    f"{bet_info_msg}"
                    f"💰 <i>အကောင့်လက်ကျန်: {current_balance} Ks</i>\n"
                )
                
                try:
                    await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=tg_message)
                except Exception as e:
                    print(f"❌ Bot Send Message Error: {e}")
                
            elif data.get('code') == 401 or "token" in str(data.get('msg')).lower():
                print("⚠️ Token Expired. ပြန်လည်ဝင်ရောက်နေပါသည်...")
                CURRENT_TOKEN = ""
                
    except Exception as e:
        print(f"❌ Game Data Request Error: {e}")

# ==========================================
# 🔄 4. BACKGROUND TASK
# ==========================================
async def auto_broadcaster():
    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
        while True:
            await check_game_and_predict(session)
            await asyncio.sleep(5) # ၅ စက္ကန့်တစ်ခါ အမြဲစစ်ဆေးမည်

# ==========================================
# 🤖 5. BOT HANDLERS (Bot ကို အသုံးပြုသူမှ ခိုင်းစေရန်)
# ==========================================
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply(
        "👋 မင်္ဂလာပါ။ Bigwin AI Predictor & Auto-Bet Bot မှ ကြိုဆိုပါတယ်။\n\n"
        "စနစ်က နောက်ကွယ်မှာ အလိုအလျောက် အလုပ်လုပ်နေပြီး Channel ထဲကို ခန့်မှန်းချက်များ ပို့ပေးနေပါတယ်။\n\n"
        "<b>Bot Commands:</b>\n"
        "/status - လက်ရှိ အကောင့်လက်ကျန်နှင့် အခြေအနေကြည့်ရန်\n"
        "/autoon - အလိုအလျောက် လောင်းကြေးထပ်ခြင်း ဖွင့်ရန်\n"
        "/autooff - အလိုအလျောက် လောင်းကြေးထပ်ခြင်း ပိတ်ရန်"
    )

@dp.message(Command("autoon"))
async def turn_auto_on(message: types.Message):
    global AUTO_BET_ENABLED, CURRENT_STEP
    AUTO_BET_ENABLED = True
    CURRENT_STEP = 0 # အဖွင့်အပိတ်လုပ်တိုင်း အစကပြန်စမည်
    await message.reply("✅ <b>Auto-Bet အား ဖွင့်လိုက်ပါပြီ!</b>\nနောက်ပွဲစဉ်မှစ၍ အလိုအလျောက် လောင်းကြေးထပ်ပါမည်။")

@dp.message(Command("autooff"))
async def turn_auto_off(message: types.Message):
    global AUTO_BET_ENABLED
    AUTO_BET_ENABLED = False
    await message.reply("❌ <b>Auto-Bet အား ပိတ်လိုက်ပါပြီ!</b>\nခန့်မှန်းချက်ကိုသာ ပို့ပေးပါမည်။")

@dp.message(Command("status"))
async def check_status(message: types.Message):
    loading_msg = await message.reply("🔄 အချက်အလက်များ ဆွဲယူနေပါသည်...")
    async with aiohttp.ClientSession() as session:
        balance = await get_user_balance(session)
        auto_status = "🟢 ဖွင့်ထားသည်" if AUTO_BET_ENABLED else "🔴 ပိတ်ထားသည်"
        current_mult = MULTIPLIERS[CURRENT_STEP] if AUTO_BET_ENABLED else 0
        
        status_text = (
            f"📊 <b>System Status</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"🔹 <b>Account :</b> <code>{USERNAME}</code>\n"
            f"🔹 <b>Balance :</b> <code>{balance}</code> Ks\n"
            f"🔹 <b>Last Issue:</b> <code>{LAST_PROCESSED_ISSUE}</code>\n"
            f"🔹 <b>Auto-Bet :</b> {auto_status}\n"
            f"🔹 <b>Current Step:</b> {current_mult} ဆ\n"
            f"🔹 <b>Bot Status:</b> 🟢 Active"
        )
        await loading_msg.edit_text(status_text)

# ==========================================
# 🚀 6. MAIN EXECUTION
# ==========================================
async def main():
    print("🚀 Aiogram Bigwin Pro-AI Bot စတင်နေပါပြီ...\n")
    
    # Background Task ကို Event Loop ထဲသို့ ထည့်ခြင်း
    asyncio.create_task(auto_broadcaster())
    
    # Bot ကို Run ခြင်း
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
