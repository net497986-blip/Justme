import os
import time
import json
import random
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import instagrapi

app = Flask(__name__)

# ===== الإعدادات من البيئة =====
TARGET_USERNAME = os.environ.get("TARGET_USER", "eziox01")
ACCOUNTS_FILE = "accounts.txt"

# ===== متغيرات حالة البوت =====
bot_status = {
    "running": False,
    "thread": None,
    "stop_flag": False,
    "logs": ["[*] جاهز. اضغط زر البدء."],
    "stats": {"success": 0, "fail": 0, "already": 0}
}

# ===== دوال الحسابات =====
def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    with open(ACCOUNTS_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [line.strip() for line in f if line.strip() and ':' in line]
    return lines

def add_account_to_file(account):
    with open(ACCOUNTS_FILE, 'a', encoding='utf-8') as f:
        f.write(account + '\n')

def delete_account_from_file(index):
    accounts = load_accounts()
    if 0 <= index < len(accounts):
        accounts.pop(index)
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(accounts))
        return True
    return False

# ===== دالة المتابعة (القلب النابض) =====
def follow_single(acc_line):
    try:
        user, pwd = acc_line.split(':', 1)
        client = instagrapi.Client()
        client.set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        client.login(user, pwd)
        
        target_id = client.user_id_from_username(TARGET_USERNAME)
        friendship = client.user_friendship(target_id)
        
        if friendship.following:
            return "already"
        
        client.user_follow(target_id)
        return "success"
    except instagrapi.exceptions.LoginRequired:
        return "fail: يطلب تحقق (2FA)"
    except instagrapi.exceptions.ChallengeRequired:
        return "fail: تحدٍ أمني"
    except Exception as e:
        return f"fail: {str(e)[:25]}"

# ===== حلقة البوت (تشتغل في خيط منفصل) =====
def bot_worker():
    global bot_status
    bot_status["running"] = True
    bot_status["stop_flag"] = False
    bot_status["stats"] = {"success": 0, "fail": 0, "already": 0}
    bot_status["logs"] = ["[+] البوت بدأ العمل."]
    
    while not bot_status["stop_flag"]:
        accounts = load_accounts()
        if not accounts:
            bot_status["logs"].append("[!] لا توجد حسابات. انتظار 5 دقائق...")
            time.sleep(300)
            continue
        
        bot_status["logs"].append(f"[>] دورة جديدة: {len(accounts)} حساب.")
        for acc in accounts:
            if bot_status["stop_flag"]:
                break
            
            username = acc.split(':', 1)[0]
            bot_status["logs"].append(f"[>] جاري محاولة: {username}...")
            result = follow_single(acc)
            
            if result == "success":
                bot_status["stats"]["success"] += 1
                bot_status["logs"].append(f"   ✅ نجح {username}")
            elif result == "already":
                bot_status["stats"]["already"] += 1
                bot_status["logs"].append(f"   ℹ️ {username} يتابع مسبقاً")
            else:
                bot_status["stats"]["fail"] += 1
                bot_status["logs"].append(f"   ❌ {username} فشل: {result}")
            
            # نوم ذكي بين ٢٠-٤٠ ثانية
            sleep_time = random.randint(20, 40)
            time.sleep(sleep_time)
        
        bot_status["logs"].append("[*] انتهت الدورة. انتظار 30 دقيقة...")
        time.sleep(1800)  # 30 دقيقة
    
    bot_status["running"] = False
    bot_status["logs"].append("[✓] البوت توقف بأمان.")

# ===== واجهة Flask (API) =====
@app.route('/')
def index():
    return render_template('index.html', target=TARGET_USERNAME, accounts=load_accounts())

@app.route('/api/status')
def get_status():
    return jsonify({
        "running": bot_status["running"],
        "stats": bot_status["stats"],
        "logs": bot_status["logs"][-30:]
    })

@app.route('/api/start', methods=['POST'])
def start_bot():
    if bot_status["running"]:
        return jsonify({"error": "البوت يعمل بالفعل"})
    thread = threading.Thread(target=bot_worker, daemon=True)
    thread.start()
    bot_status["thread"] = thread
    return jsonify({"message": "تم تشغيل البوت"})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    if not bot_status["running"]:
        return jsonify({"error": "البوت متوقف"})
    bot_status["stop_flag"] = True
    return jsonify({"message": "جاري إيقاف البوت..."})

@app.route('/api/accounts', methods=['POST'])
def add_account():
    data = request.json
    acc = data.get('account', '').strip()
    if not acc or ':' not in acc:
        return jsonify({"error": "صيغة خاطئة. استخدم user:pass"})
    accounts = load_accounts()
    if acc in accounts:
        return jsonify({"error": "الحساب موجود مسبقاً"})
    add_account_to_file(acc)
    return jsonify({"message": "تم الإضافة"})

@app.route('/api/accounts/<int:index>', methods=['DELETE'])
def remove_account(index):
    if delete_account_from_file(index):
        return jsonify({"message": "تم الحذف"})
    return jsonify({"error": "رقم غير صحيح"})

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
