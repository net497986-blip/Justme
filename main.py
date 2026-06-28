import os
import json
from flask import Flask, render_template, jsonify

app = Flask(__name__)

DATA_DIR = "data"

# ===== دوال تحميل البيانات =====
def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

# ===== نقاط النهاية (API) =====
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/darkweb')
def get_darkweb():
    return jsonify(load_json("darkweb_links.json"))

@app.route('/api/netflix')
def get_netflix():
    return jsonify(load_json("netflix_leaks.json"))

@app.route('/api/email')
def get_email():
    return jsonify(load_json("email_leaks.json"))

@app.route('/api/tools')
def get_tools():
    return jsonify(load_json("hacking_tools.json"))

@app.route('/api/instagram')
def get_instagram():
    return jsonify(load_json("instagram_accounts.json"))

@app.route('/api/prompts')
def get_prompts():
    return jsonify(load_json("prompts.json"))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
