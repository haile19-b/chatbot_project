from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import os
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

app = Flask(__name__)

# Configuration
CLIENT_SECRETS_FILE = os.path.join(os.getcwd(), 'client_secrets.json')
DATABASE = 'users.db'

# Secret keys and API keys
app.secret_key = "your_flask_secret_key"
GEMINI_API_KEY = "My_gemini_API_KEY"  # Gemini API key for the AI service
GOOGLE_CLIENT_ID = "your_google_client_id" 
GOOGLE_CLIENT_SECRET = "your_google_client_secret"
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Initialize the Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


# Database connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/')
def index():
    return render_template('index.html')


# User login functionality
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()

        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['username']
            return redirect(url_for('chat'))

        return "Invalid username or password", 401

    return render_template('login.html')


# User signup functionality
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']

        if password != confirm_password:
            return "Passwords do not match"

        hashed_password = generate_password_hash(password)
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, hashed_password))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Username already exists"

    return render_template('signup.html')


# Google OAuth2 login functionality
@app.route('/login/google')
def google_login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=["openid", "email", "profile"],
        redirect_uri=url_for('google_login_callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(prompt='consent')
    session['state'] = state
    return redirect(authorization_url)


@app.route('/login/google/callback')
def google_login_callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=["openid", "email", "profile"],
        state=state,
        redirect_uri=url_for('google_login_callback', _external=True)
    )
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    request_session = requests.Session()
    request_session.headers["Authorization"] = f"Bearer {credentials.token}"

    userinfo_endpoint = "https://openidconnect.googleapis.com/v1/userinfo"
    response = request_session.get(userinfo_endpoint)
    user_info = response.json()

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE google_id = ?', (user_info["sub"],)).fetchone()

    if not user:
        db.execute(
            'INSERT INTO users (google_id, username, email) VALUES (?, ?, ?)',
            (user_info["sub"], user_info["given_name"], user_info["email"])
        )
        db.commit()

    session['user_id'] = user_info["sub"]
    session['user_name'] = user_info["given_name"]
    session['user_email'] = user_info["email"]

    return redirect(url_for('chat'))


@app.route('/chat', methods=['GET'])
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    user_id = session['user_id']
    chats = db.execute('SELECT id, chat_name FROM chats WHERE user_id = ?', (user_id,)).fetchall()
    chats_list = [dict(chat) for chat in chats]
    return render_template('chat.html', chats=chats_list, username=session.get('user_name'))


@app.route('/new_chat', methods=['POST'])
def new_chat():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    user_id = session['user_id']
    chat_name = request.json.get('chat_name')

    if not chat_name:
        return jsonify({"success": False, "error": "Chat name is required"}), 400

    db = get_db()
    try:
        db.execute('INSERT INTO chats (user_id, chat_name, chat_history) VALUES (?, ?, ?)', (user_id, chat_name, ""))
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to create chat: {e}"}), 500


@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']
    chat_id = request.json.get('chat_id')
    message = request.json.get('message')

    if not chat_id or not message:
        return jsonify({"error": "Invalid data"}), 400

    try:
        response = model.generate_content(message)
        bot_response = response.text
    except Exception as e:
        bot_response = f"An error occurred: {e}"

    db = get_db()
    try:
        db.execute(
            'UPDATE chats SET chat_history = chat_history || ? WHERE id = ?',
            (f"User: {message}\nBot: {bot_response}\n", chat_id)
        )
        db.commit()
    except Exception as e:
        return jsonify({"error": f"Failed to store message: {e}"}), 500

    return jsonify({"bot_response": bot_response})


@app.route('/get_chat/<int:chat_id>', methods=['GET'])
def get_chat(chat_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    user_id = session['user_id']
    db = get_db()
    chat = db.execute('SELECT chat_history FROM chats WHERE id = ? AND user_id = ?', (chat_id, user_id)).fetchone()

    if chat is None:
        return jsonify({"success": False, "error": "Chat not found"}), 404

    return jsonify({"success": True, "chat_history": chat['chat_history']})


@app.route('/delete_chat/<int:chat_id>', methods=['POST'])
def delete_chat(chat_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    db = get_db()
    try:
        db.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
