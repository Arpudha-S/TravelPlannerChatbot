import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # Fixes OpenMP libiomp5md.dll conflict

import warnings
warnings.filterwarnings("ignore", message="'pin_memory' argument is set as true")
import uuid
import io, sqlite3
import fitz  # PyMuPDF
import cv2
import numpy as np
import requests
import datetime
from PIL import Image
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_file, Response
from flask_cors import CORS
import easyocr
import json
from urllib.parse import quote_plus
from apscheduler.schedulers.background import BackgroundScheduler
from disaster_warnings import disaster_warnings, location_to_country
from sources import TRUSTED_SOURCES, fetch_summary, google_fallback
from dbschema import save_scraped_data, get_all_scraped_data, init_db, verify_admin
from chathistory import init_chat_db, save_chat, get_chat_history, list_all_sessions
from werkzeug.security import check_password_hash, generate_password_hash
from vector import add_to_vector_db, search_vector_db
from llm_answer import generate_answer, is_in_scope, recent_cache, health_check_deepseek
from weather_api import fetch_weather_data 

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
CORS(app)
init_db()
init_chat_db()
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
reader = easyocr.Reader(['en'])
CHAT_HISTORY_DB = "chat_history.db"
CONFIG_FILE = "config.json"
with open("config.json", "r") as f:
    config = json.load(f)
OUT_OF_SCOPE_MSG = config.get("out_of_scope_message", "Sorry, I can only assist with travel-related queries.")

# Session store
sessions = {}
user_requested_cities = set()

#UI
@app.route('/')
def index():
    return render_template('travelbot.html')

#Chat History
@app.route('/load-history', methods=['POST'])
def load_history():
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'session_id is required'}), 400

    conn = sqlite3.connect(CHAT_HISTORY_DB)
    c = conn.cursor()
    c.execute('''
        SELECT user_input, bot_response, timestamp
        FROM chat_history
        WHERE session_id = ?
        ORDER BY timestamp
    ''', (session_id,))
    rows = c.fetchall()
    conn.close()
    history =[]
    for user_input, bot_response, timestamp in rows:
        if user_input:
            history.append({'sender': 'user', 'text': user_input, 'timestamp': timestamp})
        if bot_response:
            history.append({'sender': 'bot', 'text': bot_response, 'timestamp': timestamp})

    return jsonify({'session_id': session_id, 'history': history})

def save_message_to_db(session_id, sender, text):
    timestamp = datetime.datetime.now().isoformat()
    user_input = text if sender == 'user' else None
    bot_response = text if sender == 'bot' else None

    conn = sqlite3.connect(CHAT_HISTORY_DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO chat_history (session_id, user_input, bot_response, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (session_id, user_input, bot_response, timestamp))
    conn.commit()
    conn.close()

@app.route('/save-message', methods=['POST'])
def save_message():
    data = request.get_json()
    session_id = data.get('session_id')
    sender = data.get('sender')
    text = data.get('text')

    if not session_id or not sender or not text:
        return jsonify({'error': 'session_id, sender, and text are required'}), 400
    timestamp = datetime.datetime.now().isoformat()
    
    if sender == 'user':
        user_input = text
        bot_response = None
    else:
        user_input = None
        bot_response = text

    conn = sqlite3.connect(CHAT_HISTORY_DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO chat_history (session_id, user_input, bot_response, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (session_id, user_input, bot_response, timestamp))
    conn.commit()
    conn.close()
    print("Saving message:", session_id, sender, text)
    return jsonify({'status': 'saved'})

@app.route('/query', methods=['POST'])
def query():
    data = request.get_json()
    question = data.get('query', '')
    model_name = data.get('model_name', 'deepseek')
    session_id = data.get('session_id')
    brochure_uploaded = data.get('brochure_uploaded', False)

    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = []

    if not isinstance(sessions[session_id], dict) or 'messages' not in sessions[session_id]:
        sessions[session_id] = {'messages': [], 'uploads': []}

    if not is_in_scope(question) and not brochure_uploaded:
        sessions[session_id]['messages'].append({'sender': 'bot', 'text': OUT_OF_SCOPE_MSG, 'type': 'out_of_scope'})
        save_message_to_db(session_id, 'bot', OUT_OF_SCOPE_MSG)
        return jsonify({
            'reply': OUT_OF_SCOPE_MSG,
            'session_id': session_id,
            'disaster_warning': "",
            'status': 'out_of_scope'
        })

    # Check for disaster warning by country keyword
    matched_warning = None
    matched_country = None
    lower_question = question.lower()
    for country in disaster_warnings:
        if country.lower() in question.lower():
            matched_country = country
            matched_warning = f"\n Disaster Warning for {country}: {disaster_warnings[country]}"
            break

    if not matched_country:
        for location, country in location_to_country.items():
            if location in lower_question:
                matched_country = country
                matched_warning = f"\nDisaster Warning for {country}: {disaster_warnings[country]}"
                break

    if matched_country:
        matched_warning = f" Disaster Warning for {matched_country}: {disaster_warnings[matched_country]}"

    # Context from Vector DB
    if brochure_uploaded:
        print("[QUERY]  Brochure mode enabled")
        doc_ids = [e['doc_id'] for e in sessions[session_id].get('uploads', [])]
        if doc_ids:
            context_chunks = []
            for doc_id in doc_ids:
                results = search_vector_db(question, doc_id_filter=doc_id)
                context_chunks += [r['text'] for r in results]
            context = "\n".join(context_chunks) if context_chunks else "No brochure context found."
        else:
            context = "No brochure found in this session."
    else:
        results = search_vector_db(question)
        context = "\n".join([r['text'] for r in results]) if results else "No general context found."

    if matched_warning:
        context += "\n\n" + matched_warning

    # Generate reply using LLM
    reply = generate_answer(question, context, model_name=model_name)
    sessions[session_id]['messages'].append({'sender': 'bot', 'text': reply})
    
    save_message_to_db(session_id, 'user', question)
    save_message_to_db(session_id, 'bot', reply)
    return jsonify({
        'reply': reply,
        'session_id': session_id,
        'disaster_warning': matched_warning if matched_warning else "",
        'status': 'ok'
    })

#Uploads
@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file:
        print("[UPLOAD] No file uploaded")
        return jsonify({'error': 'No file uploaded'}), 400

    filename = file.filename.lower()
    print(f"[UPLOAD] 📄 Received file: {filename}")
    text = ""

    if filename.endswith('.pdf'):
        print("[UPLOAD] Processing as PDF")
        doc = fitz.open(stream=file.read(), filetype="pdf")
        all_text = ""
        for page_num in range(len(doc)):
            pix = doc[page_num].get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            img_array = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            results = reader.readtext(img_array, detail=0)
            page_text = "\n".join(results)
            print(f"[OCR] Page {page_num + 1} text length: {len(page_text)}")
            all_text += f"\n--- Page {page_num + 1} ---\n{page_text}"
        text = all_text

    elif filename.endswith(('.png', '.jpg', '.jpeg')):
        print("[UPLOAD] 🖼️ Processing as image")
        img = Image.open(file.stream)
        img_array = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        results = reader.readtext(img_array, detail=0)
        text = "\n".join(results)
        print(f"[OCR] Image text length: {len(text)}")

    else:
        print("[UPLOAD] Unsupported file format")
        return jsonify({"content": "Unsupported file format"}), 415

    if not is_in_scope(text):
        print("[UPLOAD]  Document rejected: Not related to travel")
        return jsonify({"status": "Rejected: Document not related to travel. Please upload travel-related brochures or images."}), 400
    doc_id = str(uuid.uuid4())
    add_to_vector_db(text.strip(), doc_id, category="brochure")

    client_session_id = request.form.get("session_id") or request.cookies.get("chat_session_id")
    if not client_session_id:
        client_session_id = str(uuid.uuid4())
    if client_session_id not in sessions or not isinstance(sessions[client_session_id], dict):
        sessions[client_session_id] = {'messages': [], 'uploads': []}
    sessions[client_session_id]['uploads'].append({"type": "upload", "doc_id": doc_id})
    print(f"[UPLOAD] Stored doc_id {doc_id} in session {client_session_id}")

    resp = jsonify({"status": "Upload successful. Ask your question based on the document."})
    resp.set_cookie("chat_session_id", client_session_id)  # Ensure cookie is set
    return resp

#web Scraping
@app.route('/scrape', methods=['POST']) 
def scrape():
    place = request.json.get('place')
    if not place:
        return jsonify({'error': 'Place is required'}), 400
    results = {}
    
    for category, base_urls in TRUSTED_SOURCES.items():
        summaries = []
        for base in base_urls:
            full_url = base + quote_plus(place)
            summary = fetch_summary(full_url)
            if summary:
                try:
                    doc_id = f"{place.lower().replace(' ', '_')}_{category}_{base.split('.')[1]}"
                    add_to_vector_db(summary, doc_id)
                except Exception as e:
                    print(f"VectorDB error for {doc_id}: {e}")

                summaries.append({'summary': summary, 'source': full_url})
                save_scraped_data(place, category, summary, full_url)
            else:
                fallback_url = google_fallback(place, category)
                summaries.append({
                    'summary': f"No readable content found, check Google results for {category}.",
                    'source': fallback_url
                })
        results[category] = summaries
    return jsonify({'status': f'Successfully fetched travel data for {place}', 'data': results})

@app.route('/refresh-weather', methods=['POST'])
def refresh_weather():
    try:
        data = request.get_json()
        cities = data.get('cities', [])

        if not cities or not isinstance(cities, list):
            return jsonify({'error': 'Please provide a list of cities'}), 400

        print(f"[DEBUG] Received cities: {cities}")
        results = []

        for city in cities:
            try:
                weather_info = fetch_weather_data(city)
                formatted = (
                    f"City: {city}\n"
                    f"Temp: {weather_info['temp']}°C\n"
                    f"Condition: {weather_info['condition']}\n"
                    f"Advisory: {weather_info['advice']}"
                )
                add_to_vector_db(formatted, city + "_" + datetime.datetime.now().isoformat(), category="weather")
                results.append({
                    "city": city,
                    "temp": weather_info['temp'],
                    "condition": weather_info['condition'],
                    "advice": weather_info['advice']
                })
            except Exception as e:
                print(f"[ERROR] Failed to fetch weather for {city}: {e}")
                results.append({
                    "city": city,
                    "error": f"Failed to fetch data: {str(e)}"
                })

        return jsonify({'status': 'Weather data refreshed and indexed.', 'data': results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
def auto_refresh_weather():
    print("[Scheduler]  Running auto weather refresh...")
    try:
        for city in list(user_requested_cities):
            weather_info = fetch_weather_data(city)
            formatted = (
                f"City: {city}\n"
                f"Temp: {weather_info['temp']}°C\n"
                f"Condition: {weather_info['condition']}\n"
                f"Advisory: {weather_info['advice']}"
            )
            add_to_vector_db(formatted, city + "_auto_" + datetime.datetime.now().isoformat(), category="weather")
        print("[Scheduler]  Weather data refreshed.")
    except Exception as e:
        print(f"[Scheduler]  Error during auto-refresh: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(auto_refresh_weather, trigger='interval', hours=1)
scheduler.start()

@app.route('/admin')
def admin():
    data = get_all_scraped_data()
    return render_template('admin.html', data=data)

def load_admin_credentials():
    with open("admin_users.json", "r") as f:
        return json.load(f)

def save_admin_credentials(users):
    with open("admin_users.json", "w") as f:
        json.dump(users, f, indent=2)

def verify_admin(username, password):
    users = load_admin_credentials()
    if username in users:
        return check_password_hash(users[username], password)
    return False

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        if verify_admin(user, pwd):
            session['admin'] = user
            return redirect(url_for('admin_dashboard'))
        else:
            error="Invalid credentials"
    return render_template('login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    print("Admin in session?", 'admin' in session)
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    tab = request.args.get('tab', 'travel')
    search = request.args.get('search', '').strip().lower()
    session_id = request.args.get('session_id')

    conn = sqlite3.connect('travel_data.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM travel_info WHERE LOWER(place) LIKE ?", ('%' + search + '%',)) if search else cursor.execute("SELECT * FROM travel_info")
    travel_rows = cursor.fetchall()
    conn.close()

    with open("apikeys.json") as f:
        api_keys = json.load(f)
    
    conn2 = sqlite3.connect(CHAT_HISTORY_DB)
    c = conn2.cursor()
    if session_id:
        c.execute("SELECT user_input, bot_response, timestamp FROM chat_history WHERE session_id = ? ORDER BY timestamp", (session_id,))
        chat_history = c.fetchall()
    else:
        chat_history = []
    c.execute("SELECT DISTINCT session_id FROM chat_history ORDER BY timestamp DESC")
    sessions = [row[0] for row in c.fetchall()]
    conn2.close()

    with open("config.json") as f:
        config=json.load(f)
    models=['deepseek', 'mistral', 'gemini']

    recent_cache_data = list(recent_cache) if 'recent_cache' in globals() else []

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_config':
            config['out_of_scope_message'] = request.form.get('out_of_scope_message', '')
            config['llm_model'] = request.form.get('llm_model', 'mistral')
            config['persistent_chat_enabled'] = 'persistent_chat_enabled' in request.form
            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)
            return redirect(url_for('admin_dashboard', tab='config'))
        
        elif action == 'add_apikey':
            key = request.form['key'].strip()
            site = request.form['site'].strip()
            expires = request.form['expires'].strip()
            with open("apikeys.json", "r") as f:
                keys = json.load(f)
            keys[key] = {
                "site": site,
                "enabled": True,
                "expires": expires
            }
            with open("apikeys.json", "w") as f:
                json.dump(keys, f, indent=2)
            return redirect(url_for('admin_dashboard', tab='apikeys'))
    return render_template('admin.html', tab=tab, rows=travel_rows, api_keys=api_keys, chat_history=chat_history, session_id=session_id, sessions=sessions,
                           config=config, models=models, search=search, recent_cache=recent_cache_data)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    message=None
    if request.method == 'POST':
        username = request.form.get('username')
        new_pwd = request.form.get('new_password')
        confirm_pwd = request.form.get('confirm_password')
        users = load_admin_credentials()

        if username not in users:
            message = "Username does not exist."
        elif new_pwd != confirm_pwd:
            message = "Passwords do not match."
        else:
            users[username] = check_password_hash(new_pwd)
            save_admin_credentials(users)
            message = "Password reset successfully. You can now log in."
            return redirect(url_for('admin_login'))
    return render_template('forgotpwd.html', message=message)

@app.route('/health')
def health_check():
    ok = health_check_deepseek()
    return jsonify({"status": "ok" if ok else "fail"}), 200 if ok else 503
    
@app.route('/admin/cache')
def view_recent_cache():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    return jsonify(list(recent_cache))

@app.route('/disaster-warning', methods=['POST'])
def disaster_warning():
    try:
        data = request.get_json()
        country = data.get('country', '').strip()

        if not country:
            return jsonify({'error': 'Please provide a country name'}), 400

        warning = disaster_warnings.get(country)
        if warning:
            return jsonify({'country': country, 'warning': warning}), 200
        else:
            return jsonify({'country': country, 'warning': 'No specific disaster warning available.'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)   