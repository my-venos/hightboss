import asyncio
import time
import os
import math
from collections import Counter
from dotenv import load_dotenv
import aiohttp
import motor.motor_asyncio 

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# --- 🧠 ENTERPRISE AI LIBRARIES ---
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
import warnings
warnings.filterwarnings("ignore")

load_dotenv()

# ==========================================
# ⚙️ 1. CONFIGURATION & GLOBALS
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("CHANNEL_ID")
MONGO_URI = os.getenv("MONGO_URI") 

bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Database Setup
db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = db_client['sixlottery_ultimate'] 
history_coll = db['game_history'] 
predict_coll = db['predictions'] 

# STICKERS
WIN_STICKER_ID = ""  
LOSE_STICKER_ID = "" 

BASE_HEADERS = {
    'authority': '6lotteryapi.com', 'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8', 'origin': 'https://www.6win566.com',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'
}

# ==========================================
# 🧠 2. THE ULTIMATE AI ENGINE (CLASSES)
# ==========================================

class AccuracyOptimizer:
    """ ⚙️ AI Model ၄ ခု၏ အမှန်/အမှားကို စောင့်ကြည့်ပြီး Weight များကို အလိုအလျောက် ချိန်ညှိပေးသော စနစ် (Self-Learning) """
    def __init__(self):
        # ကနဦး ယုံကြည်မှု ရာခိုင်နှုန်းများ
        self.weights = {'rf': 0.3, 'gb': 0.3, 'markov': 0.2, 'pattern': 0.2}
        self.performance_history = [] # မည်သည့် မော်ဒယ်က အမှန်ဆုံးလဲ မှတ်သားရန်

    def update_weights(self, actual_result, predictions):
        """ ပွဲပြီးတိုင်း မည်သည့် Algorithm မှန်သလဲ စစ်ဆေးပြီး အလေးချိန် (Weight) ကို အလိုအလျောက် ပြင်မည် """
        total_weight = 0
        for model_name, pred in predictions.items():
            if pred == actual_result:
                self.weights[model_name] += 0.05 # မှန်လျှင် Weight တိုးမည်
            else:
                self.weights[model_name] = max(0.05, self.weights[model_name] - 0.02) # မှားလျှင် Weight လျှော့မည်
            total_weight += self.weights[model_name]
        
        # Normalize (ပေါင်းလိုက်လျှင် 1.0 ပြန်ဖြစ်အောင် ညှိခြင်း)
        for k in self.weights:
            self.weights[k] /= total_weight

class PatternAI:
    """ 🔍 သမိုင်းကြောင်းမှ ထပ်ခါထပ်ခါ ဖြစ်ပေါ်နေသော Sequence များကို ရှာဖွေသော စနစ် """
    @staticmethod
    def extract_ngram_pattern(sizes, n=4):
        if len(sizes) < n + 1: return 0.5, 0.5
        current_pattern = tuple(sizes[-n:])
        matches = {'BIG': 0, 'SMALL': 0}
        
        for i in range(len(sizes) - n):
            if tuple(sizes[i:i+n]) == current_pattern:
                next_size = sizes[i+n]
                matches[next_size] += 1
                
        total = matches['BIG'] + matches['SMALL']
        if total == 0: return 0.5, 0.5
        return matches['BIG'] / total, matches['SMALL'] / total

class AutoMultiplierStrategy:
    """ 💰 ယုံကြည်မှု (Confidence) နှင့် ရှုံးပွဲ (Streak) ပေါ်မူတည်၍ အကောင်းဆုံး အဆကို တွက်ထုတ်သောစနစ် """
    @staticmethod
    def get_optimal_multiplier(lose_streak, confidence):
        # အခြေခံ Martingale ပုံစံ (၁၊ ၂၊ ၃၊ ၅၊ ၈၊ ၁၃၊ ၂၁) - Fibonacci Hybrid
        base_multipliers = [1, 2, 3, 5, 8, 13, 21, 34]
        
        if lose_streak >= len(base_multipliers):
            lose_streak = 0 # ပြတ်သွားပါက ပြန်စမည်
            
        base_muti = base_multipliers[lose_streak]
        
        # 💡 [Smart Adjustment] AI ၏ ယုံကြည်မှု အလွန်မြင့်မားနေပါက အဆကို အနည်းငယ် ပိုတင်ပေးမည်
        if confidence >= 85.0 and lose_streak <= 3:
            return base_muti + 1
        # ယုံကြည်မှု နည်းပါက အဆမတင်ဘဲ ကာကွယ်မည်
        elif confidence < 60.0 and lose_streak > 0:
            return max(1, base_muti - 1)
            
        return base_muti

class UltimateAI:
    """ 🤖 Master Core: အရာအားလုံးကို ပေါင်းစပ်၍ ဆုံးဖြတ်ချက်ချသော နေရာ """
    def __init__(self):
        self.optimizer = AccuracyOptimizer()
        self.last_predictions = {} # Weight ချိန်ရန် နောက်ဆုံးခန့်မှန်းချက်များကို သိမ်းထားမည်
        self.cache_issue = None
        self.cache_result = None

    def predict(self, history_docs):
        if len(history_docs) < 50:
            return "BIG", 50.0, 1
            
        sizes = [d.get('size', 'BIG') for d in docs]
        numbers = [int(d.get('number', 0)) for d in docs]
        parities = [1 if d.get('parity', 'EVEN') == 'EVEN' else 0 for d in docs]
        
        # 1. Pattern AI (N-Gram)
        pat_b_prob, pat_s_prob = PatternAI.extract_ngram_pattern(sizes, n=3)
        self.last_predictions['pattern'] = 'BIG' if pat_b_prob > pat_s_prob else 'SMALL'

        # 2. Markov Chain (State Transition)
        transitions = {'BIG': {'BIG': 0, 'SMALL': 0}, 'SMALL': {'BIG': 0, 'SMALL': 0}}
        for i in range(len(sizes)-1): transitions[sizes[i]][sizes[i+1]] += 1
        curr = sizes[-1]
        tot_trans = transitions[curr]['BIG'] + transitions[curr]['SMALL']
        mar_b_prob = transitions[curr]['BIG'] / tot_trans if tot_trans > 0 else 0.5
        mar_s_prob = transitions[curr]['SMALL'] / tot_trans if tot_trans > 0 else 0.5
        self.last_predictions['markov'] = 'BIG' if mar_b_prob > mar_s_prob else 'SMALL'

        # 3. Machine Learning (RF & GB)
        X, y, window = [], [], 5 
        for i in range(len(sizes) - window):
            row = []
            for j in range(window): 
                val = 1 if sizes[i+j] == 'BIG' else 0
                row.extend([val, numbers[i+j], parities[i+j]])
            X.append(row); y.append(1 if sizes[i+window] == 'BIG' else 0)
            
        rf_b_prob, gb_b_prob = 0.5, 0.5
        if len(X) > 30:
            rf = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42).fit(X, y)
            gb = GradientBoostingClassifier(n_estimators=100, learning_rate=0.05, max_depth=3).fit(X, y)
            
            curr_feats = []
            for j in range(1, window + 1): 
                val = 1 if sizes[-j] == 'BIG' else 0
                curr_feats.extend([val, numbers[-j], parities[-j]])
                
            rf_probs = rf.predict_proba([curr_feats])[0]
            gb_probs = gb.predict_proba([curr_feats])[0]
            
            rf_b_prob = rf_probs[list(rf.classes_).index(1)] if 1 in rf.classes_ else 0.0
            gb_b_prob = gb_probs[list(gb.classes_).index(1)] if 1 in gb.classes_ else 0.0
            
        self.last_predictions['rf'] = 'BIG' if rf_b_prob > 0.5 else 'SMALL'
        self.last_predictions['gb'] = 'BIG' if gb_b_prob > 0.5 else 'SMALL'

        # --- ⚙️ ENSEMBLE VOTING WITH OPTIMIZED WEIGHTS ---
        w = self.optimizer.weights
        final_b_score = (rf_b_prob * w['rf']) + (gb_b_prob * w['gb']) + (mar_b_prob * w['markov']) + (pat_b_prob * w['pattern'])
        final_s_score = ((1-rf_b_prob) * w['rf']) + ((1-gb_b_prob) * w['gb']) + (mar_s_prob * w['markov']) + (pat_s_prob * w['pattern'])
        
        # 💡 [Anti-Long-Streak Logic]
        # အတန်းရှည်လွန်းပါက ချိုးမည့်အစား ဆက်လိုက်ရန် Weight ကို အတင်းပြောင်းမည်
        current_streak = 1
        for i in range(len(sizes)-2, -1, -1):
            if sizes[i] == sizes[-1]: current_streak += 1
            else: break
            
        if current_streak >= 5:
            if sizes[-1] == 'BIG': final_b_score += 0.3
            else: final_s_score += 0.3

        final_pred = "BIG" if final_b_score > final_s_score else "SMALL"
        
        # Confidence Score Calculation (50% to 99%)
        raw_confidence = (max(final_b_score, final_s_score) / (final_b_score + final_s_score)) * 100
        confidence = min(max(raw_confidence, 51.0), 99.0)
        
        return final_pred, round(confidence, 1)

# Global Instance
ai_engine = UltimateAI()
STATE = {"last_issue": None, "lose_streak": 0}

# ==========================================
# 🚀 3. BOT CONTROLLER & MAIN LOOP
# ==========================================
async def fetch_api(session):
    json_data = {'pageSize': 10, 'pageNo': 1, 'typeId': 1, 'language': 7, 'random': '736ea5fe7d1744008714320d2cfbbed4', 'signature': '9BE5D3A057D1938B8210BA32222A993C', 'timestamp': int(time.time())}
    for _ in range(3):
        try:
            async with session.post('https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList', headers=BASE_HEADERS, json=json_data, timeout=3.0) as r:
                if r.status == 200: return await r.json()
        except: await asyncio.sleep(0.5)
    return None

async def game_loop():
    await init_db()
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                data = await fetch_api(session)
                if not data or data.get('code') != 0:
                    await asyncio.sleep(1); continue
                    
                records = data.get("data", {}).get("list", [])
                if not records: continue
                
                latest = records[0]
                issue, number = str(latest["issueNumber"]), int(latest["number"])
                size = "BIG" if number >= 5 else "SMALL"
                parity = "EVEN" if number % 2 == 0 else "ODD"
                
                # အစပြုခြင်း (Initialization)
                if not STATE["last_issue"]:
                    STATE["last_issue"] = issue
                    # Calculate initial streak from DB
                    recent = await predict_coll.find({"win_lose": {"$ne": None}}).sort("issue_number", -1).limit(10).to_list(length=10)
                    for p in recent:
                        if p.get("win_lose") == "LOSE": STATE["lose_streak"] += 1
                        else: break
                    
                    next_issue = str(int(issue) + 1)
                    global docs
                    docs = await history_coll.find().sort("issue_number", -1).limit(500).to_list(length=500)
                    
                    pred, conf = ai_engine.predict(docs)
                    multi = AutoMultiplierStrategy.get_optimal_multiplier(STATE["lose_streak"], conf)
                    
                    msg = f"<b>[ULTIMATE AI PRO V5]</b>\n⏰ Period: {next_issue}\n🎯 Prediction: {pred} {multi}x\n📊 Confidence: {conf}%\n⚙️ Optimizer: Active"
                    await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=msg)
                    await asyncio.sleep(1); continue

                # ပွဲစဉ်အသစ် ထွက်လာသောအခါ
                if int(issue) > int(STATE["last_issue"]):
                    await history_coll.update_one({"issue_number": issue}, {"$setOnInsert": {"number": number, "size": size, "parity": parity}}, upsert=True)
                    
                    # Self-Learning Update: ယခင်ပွဲရလဒ် အမှန်ကို AI သို့ ပေးပို့၍ Weights များ ညှိခြင်း
                    ai_engine.optimizer.update_weights(size, ai_engine.last_predictions)
                    
                    # အရင်ပွဲ ခန့်မှန်းချက် မှန်/မမှန် စစ်ဆေးခြင်း
                    pred_doc = await predict_coll.find_one({"issue_number": issue})
                    if pred_doc and pred_doc.get("predicted_size"):
                        predicted_size = pred_doc["predicted_size"]
                        is_win = (predicted_size == size)
                        win_lose_db = "WIN" if is_win else "LOSE"
                        
                        await predict_coll.update_one({"issue_number": issue}, {"$set": {"actual_size": size, "actual_number": number, "win_lose": win_lose_db}})
                        
                        # ရလဒ်ပို့ခြင်း
                        icon = "🟢" if is_win else "🔴"
                        res_letter = "B" if size == "BIG" else "S"
                        multi = AutoMultiplierStrategy.get_optimal_multiplier(STATE["lose_streak"], pred_doc.get("confidence", 50.0))
                        
                        res_msg = (
                            f"<b>SIX-LOTTERY</b>\n\n"
                            f"⏰ Period: {issue}\n"
                            f"🎯 Choice: {predicted_size} {multi}x\n"
                            f"📊 Result: {icon} {win_lose_db} | {res_letter} ({number})"
                        )
                        await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=res_msg)
                        
                        # Sticker ပို့ခြင်း
                        try:
                            if is_win and WIN_STICKER_ID: await bot.send_sticker(chat_id=TELEGRAM_CHANNEL_ID, sticker=WIN_STICKER_ID)
                            elif not is_win and LOSE_STICKER_ID: await bot.send_sticker(chat_id=TELEGRAM_CHANNEL_ID, sticker=LOSE_STICKER_ID)
                        except: pass
                        
                        # Update Streak
                        if is_win: STATE["lose_streak"] = 0
                        else: STATE["lose_streak"] += 1

                    STATE["last_issue"] = issue
                    
                    # 🎯 နောက်ပွဲစဉ်အတွက် တွက်ချက်ခြင်း
                    next_issue = str(int(issue) + 1)
                    docs = await history_coll.find().sort("issue_number", -1).limit(500).to_list(length=500)
                    
                    pred, conf = ai_engine.predict(docs)
                    await predict_coll.update_one({"issue_number": next_issue}, {"$set": {"predicted_size": pred, "confidence": conf}}, upsert=True)
                    
                    multi = AutoMultiplierStrategy.get_optimal_multiplier(STATE["lose_streak"], conf)
                    
                    # 💡 Optimizer လုပ်ဆောင်နေကြောင်း ပြသရန်
                    top_model = max(ai_engine.optimizer.weights, key=ai_engine.optimizer.weights.get)
                    
                    pred_msg = (
                        f"<b>[ULTIMATE AI PRO V5]</b>\n"
                        f"⏰ Period: {next_issue}\n"
                        f"🎯 Prediction: {pred} {multi}x\n"
                        f"📊 Confidence: {conf}%\n"
                        f"🧠 Top Core: {top_model.upper()}"
                    )
                    await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=pred_msg)

            except Exception as e:
                print(f"Loop Error: {e}")
            await asyncio.sleep(1.5)

async def main():
    print("🚀 ULTIMATE AI PRO V5 (Self-Learning + Pattern + AutoMultiplier) is starting...\n")
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(game_loop())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot Stopped.")
