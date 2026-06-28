import os
import time
import json
import random
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import instagrapi

app = Flask(__name__)

# ===== الإعدادات =====
TARGET_USERNAME = os.environ.get("TARGET_USER", "")
ACCOUNTS_FILE = "accounts.txt"
bot_status = {
    "running": False,
    "thread": None,
    "stop_flag": False,
    "logs": [],
    "stats": {"success": 0, "fail": 0, "already": 0},
    "details": []  # قائمة تفصيلية لكل حساب
}
target_lock = threading.Lock()
current_target = TARGET_USERNAME

# ===== دوال الحسابات =====
def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    with open(ACCOUNTS_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        return [line.strip() for line in f if line.strip() and ':' in line]

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

# ===== دالة المتابعة مع تفاصيل الفشل =====
def follow_single(acc_line):
    try:
        user, pwd = acc_line.split(':', 1)
        client = instagrapi.Client()
        client.set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        client.login(user, pwd)
        
        with target_lock:
            target = current_target
        if not target:
            return "fail: لم يتم تحديد هدف"
        
        target_id = client.user_id_from_username(target)
        friendship = client.user_friendship(target_id)
        
        if friendship.following:
            return "already"
        
        client.user_follow(target_id)
        return "success"
    except instagrapi.exceptions.LoginRequired:
        return "fail: يتطلب تحقق (2FA)"
    except instagrapi.exceptions.ChallengeRequired:
        return "fail: تحدٍ أمني (كابتشا)"
    except instagrapi.exceptions.ClientLoginError as e:
        if "password" in str(e).lower():
            return "fail: كلمة مرور خاطئة"
        return f"fail: خطأ دخول ({str(e)[:20]})"
    except Exception as e:
        return f"fail: {str(e)[:30]}"

# ===== حلقة البوت =====
def bot_worker():
    global bot_status
    bot_status["running"] = True
    bot_status["stop_flag"] = False
    bot_status["stats"] = {"success": 0, "fail": 0, "already": 0}
    bot_status["details"] = []
    bot_status["logs"] = ["[+] البوت بدأ العمل."]
    
    while not bot_status["stop_flag"]:
        accounts = load_accounts()
        if not accounts:
            bot_status["logs"].append("[!] لا توجد حسابات. انتظار 3 دقائق...")
            time.sleep(180)
            continue
        
        bot_status["logs"].append(f"[>] دورة جديدة: {len(accounts)} حساب.")
        for acc in accounts:
            if bot_status["stop_flag"]:
                break
            username = acc.split(':', 1)[0]
            bot_status["logs"].append(f"[>] جاري: {username}...")
            result = follow_single(acc)
            detail = {"account": acc, "result": result, "time": datetime.now().strftime("%H:%M:%S")}
            bot_status["details"].append(detail)
            if result == "success":
                bot_status["stats"]["success"] += 1
                bot_status["logs"].append(f"   ✅ {username} نجح")
            elif result == "already":
                bot_status["stats"]["already"] += 1
                bot_status["logs"].append(f"   ℹ️ {username} يتابع مسبقاً")
            else:
                bot_status["stats"]["fail"] += 1
                bot_status["logs"].append(f"   ❌ {username} فشل: {result}")
            
            time.sleep(random.randint(15, 35))
        
        bot_status["logs"].append("[*] انتهت الدورة. انتظار 15 دقيقة...")
        time.sleep(900)  # 15 دقيقة
    
    bot_status["running"] = False
    bot_status["logs"].append("[✓] البوت توقف.")

# ===== نقاط نهاية Flask =====
@app.route('/')
def index():
    with target_lock:
        target = current_target
    return render_template('index.html', target=target, accounts=load_accounts())

@app.route('/api/status')
def get_status():
    return jsonify({
        "running": bot_status["running"],
        "stats": bot_status["stats"],
        "logs": bot_status["logs"][-30:],
        "details": bot_status["details"][-50:]
    })

@app.route('/api/start', methods=['POST'])
def start_bot():
    if bot_status["running"]:
        return jsonify({"error": "البوت يعمل بالفعل"})
    # تحقق من وجود هدف
    with target_lock:
        if not current_target:
            return jsonify({"error": "الرجاء تعيين الهدف أولاً"})
    thread = threading.Thread(target=bot_worker, daemon=True)
    thread.start()
    bot_status["thread"] = thread
    return jsonify({"message": "تم تشغيل البوت"})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    if not bot_status["running"]:
        return jsonify({"error": "البوت متوقف"})
    bot_status["stop_flag"] = True
    return jsonify({"message": "جاري الإيقاف..."})

@app.route('/api/set_target', methods=['POST'])
def set_target():
    data = request.json
    new_target = data.get('target', '').strip()
    if not new_target:
        return jsonify({"error": "الرجاء إدخال اسم مستخدم"})
    with target_lock:
        global current_target
        current_target = new_target
    return jsonify({"message": f"تم تعيين الهدف إلى {new_target}"})

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
