#!/usr/bin/env python3
# Instagram Bot - Web Dashboard Edition by Just-Lisa
import os
import json
import time
import random
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import instagrapi

app = Flask(__name__)

# ===== الإعدادات =====
TARGET_USERNAME = os.environ.get("TARGET_USER", "eziox01")
ACCOUNTS_FILE = "accounts.txt"
STATUS_FILE = "status.json"

# ===== حالة البوت (تخزين مؤقت) =====
bot_status = {
    "running": False,
    "thread": None,
    "stop_flag": False,
    "logs": [],
    "stats": {"success": 0, "fail": 0, "already": 0}
}

# ===== دوال تحميل وحفظ الحسابات =====
def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    with open(ACCOUNTS_FILE, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, 'w') as f:
        f.write('\n'.join(accounts))

# ===== دالة المتابعة (تعمل في الخلفية) =====
def follow_target(acc):
    try:
        client = instagrapi.Client()
        user, pwd = acc.split(':', 1)
        client.login(user, pwd)
        user_id = client.user_id_from_username(TARGET_USERNAME)
        if client.user_friendship(user_id).following:
            return "already"
        client.user_follow(user_id)
        return "success"
    except Exception as e:
        return f"fail: {str(e)[:30]}"

# ===== حلقة البوت الرئيسية (تشغل في Thread منفصل) =====
def bot_worker():
    global bot_status
    bot_status["running"] = True
    bot_status["stop_flag"] = False
    bot_status["stats"] = {"success": 0, "fail": 0, "already": 0}
    bot_status["logs"] = []
    
    bot_status["logs"].append(f"[+] Bot started at {datetime.now()}")
    
    while not bot_status["stop_flag"]:
        accounts = load_accounts()
        if not accounts:
            bot_status["logs"].append("[!] No accounts found. Waiting...")
            time.sleep(60)
            continue
        
        bot_status["logs"].append(f"[>] Cycle started with {len(accounts)} accounts.")
        for acc in accounts:
            if bot_status["stop_flag"]:
                break
            bot_status["logs"].append(f"[>] Trying {acc.split(':')[0]}...")
            result = follow_target(acc)
            if "success" in result:
                bot_status["stats"]["success"] += 1
                bot_status["logs"].append(f"    ✅ Success")
            elif result == "already":
                bot_status["stats"]["already"] += 1
                bot_status["logs"].append(f"    ℹ️ Already")
            else:
                bot_status["stats"]["fail"] += 1
                bot_status["logs"].append(f"    ❌ {result}")
            
            # نوم عشوائي
            time.sleep(random.randint(15, 30))
        
        bot_status["logs"].append(f"[*] Cycle finished. Sleeping 30 min...")
        time.sleep(1800)  # 30 دقيقة
    
    bot_status["running"] = False
    bot_status["logs"].append("[✓] Bot stopped.")

# ===== Routes Flask (الواجهة) =====
@app.route('/')
def index():
    return render_template('index.html', 
                           target=TARGET_USERNAME,
                           accounts=load_accounts())

@app.route('/api/status')
def get_status():
    return jsonify({
        "running": bot_status["running"],
        "stats": bot_status["stats"],
        "logs": bot_status["logs"][-20:]  # آخر ٢٠ سطر
    })

@app.route('/api/start', methods=['POST'])
def start_bot():
    global bot_status
    if bot_status["running"]:
        return jsonify({"error": "Bot is already running!"})
    thread = threading.Thread(target=bot_worker, daemon=True)
    thread.start()
    bot_status["thread"] = thread
    return jsonify({"message": "Bot started!"})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    global bot_status
    if not bot_status["running"]:
        return jsonify({"error": "Bot is not running!"})
    bot_status["stop_flag"] = True
    return jsonify({"message": "Stopping bot..."})

@app.route('/api/accounts', methods=['POST'])
def add_account():
    data = request.json
    account = data.get('account', '').strip()
    if not account or ':' not in account:
        return jsonify({"error": "Invalid format! Use user:pass"})
    accounts = load_accounts()
    if account in accounts:
        return jsonify({"error": "Account already exists!"})
    accounts.append(account)
    save_accounts(accounts)
    return jsonify({"message": "Account added!"})

@app.route('/api/accounts/<int:index>', methods=['DELETE'])
def delete_account(index):
    accounts = load_accounts()
    if 0 <= index < len(accounts):
        accounts.pop(index)
        save_accounts(accounts)
        return jsonify({"message": "Account deleted!"})
    return jsonify({"error": "Invalid index!"})

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
