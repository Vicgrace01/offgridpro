# web_app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import bcrypt
import json
import random
import re
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'offgridpro_super_secret_key_2026'
socketio = SocketIO(app, cors_allowed_origins="*")

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

DB_PATH = 'offgridpro.db'

# ==============================
# Database helpers
# ==============================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # Users table (profiles)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            location TEXT,
            capacity TEXT,
            excess TEXT,
            phone TEXT,
            business TEXT
        )
    ''')
    # Accounts table (login)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            role TEXT CHECK(role IN ('admin','producer','consumer'))
        )
    ''')
    # Trades table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            producer TEXT,
            consumer TEXT,
            watt_hours REAL,
            kwh REAL,
            price_per_kwh REAL,
            total_price REAL,
            status TEXT,
            created_at TEXT,
            blockchain_tx TEXT,
            sms_sent INTEGER DEFAULT 0
        )
    ''')
    # Blockchain ledger
    conn.execute('''
        CREATE TABLE IF NOT EXISTS blockchain (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT,
            tx_hash TEXT,
            block INTEGER,
            amount REAL,
            timestamp TEXT,
            status TEXT
        )
    ''')
    conn.commit()

    # Define default users
    default_users = [
        ('mr_ade', 'Mr. Adebayo', 'producer', 'Awkunanaw, Enugu', '5kW', '4.5kWh', '+2348012345678', ''),
        ('mama_bose', 'Mama Bose', 'consumer', 'Awkunanaw, Enugu', '', '', '+2348087654321', 'Shop'),
        ('chief_okonkwo', 'Chief Okonkwo', 'producer', 'GRA, Enugu', '7kW', '6.2kWh', '+2348091122334', ''),
        ('mr_emeka', 'Mr. Emeka', 'consumer', 'GRA, Enugu', '', '', '+2348065544332', 'Phone Center'),
        ('dr_nwachukwu', 'Dr. Nwachukwu', 'producer', 'Independence Layout, Enugu', '6kW', '5.0kWh', '+2348039876543', ''),
        ('mrs_obi', 'Mrs. Obi', 'consumer', 'Independence Layout, Enugu', '', '', '+2348074567890', 'Restaurant'),
        ('mr_okafor', 'Mr. Okafor', 'producer', 'New Haven, Enugu', '5kW', '3.8kWh', '+2348012345679', ''),
        ('mrs_amadi', 'Mrs. Amadi', 'consumer', 'New Haven, Enugu', '', '', '+2348056789012', 'Cold Room')
    ]

    # Insert default users if table is empty
    cur = conn.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        conn.executemany('''
            INSERT INTO users (id, name, type, location, capacity, excess, phone, business)
            VALUES (?,?,?,?,?,?,?,?)
        ''', default_users)

    # Insert admin account if not exists
    cur = conn.execute("SELECT COUNT(*) FROM accounts WHERE email = 'admin@offgridpro.com'")
    if cur.fetchone()[0] == 0:
        admin_pw = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
        conn.execute("INSERT INTO accounts (user_id, email, password_hash, role) VALUES (?,?,?,?)",
                     ('admin', 'admin@offgridpro.com', admin_pw, 'admin'))

    # Insert default producer/consumer accounts (password = 'password123')
    for user in default_users:
        if user[2] in ('producer','consumer'):
            email = f"{user[0]}@offgridpro.com"
            cur = conn.execute("SELECT COUNT(*) FROM accounts WHERE email = ?", (email,))
            if cur.fetchone()[0] == 0:
                pw = bcrypt.hashpw('password123'.encode('utf-8'), bcrypt.gensalt())
                conn.execute("INSERT INTO accounts (user_id, email, password_hash, role) VALUES (?,?,?,?)",
                             (user[0], email, pw, user[2]))

    conn.commit()
    conn.close()

# ==============================
# User class for Flask-Login
# ==============================

class User(UserMixin):
    def __init__(self, id, user_id, email, role):
        self.id = id
        self.user_id = user_id
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM accounts WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user['id'], user['user_id'], user['email'], user['role'])
    return None

# ==============================
# Helper functions
# ==============================

def get_user_location(user_id):
    loc_map = {
        'Awkunanaw': (6.4400, 7.5000),
        'Asata': (6.4450, 7.4900),
        'Ogui': (6.4550, 7.4950),
        'Uwani': (6.4350, 7.4850),
        'New Haven': (6.4650, 7.5050),
        'Independence Layout': (6.4500, 7.5100),
        'GRA': (6.4600, 7.4800),
        'Abakpa': (6.4700, 7.5200),
        'Emene': (6.4800, 7.5300),
        'Agbani': (6.4200, 7.4600),
        'Nike': (6.4900, 7.5400),
        'Achara Layout': (6.4380, 7.4980),
        'Trans-Ekulu': (6.4680, 7.4750),
        'Ugwuaji': (6.4100, 7.4700)
    }
    conn = get_db()
    user = conn.execute("SELECT location FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        loc_name = user['location'].split(',')[0].strip()
        return loc_map.get(loc_name, (6.4542, 7.4940))
    return (6.4542, 7.4940)

def create_trade(producer_name, consumer_name, watt_hours):
    disco_price_per_kwh = 160
    p2p_price = disco_price_per_kwh * 0.85
    total_price = (watt_hours / 1000) * p2p_price
    trade_id = f'ENU_{datetime.now().strftime("%Y%m%d%H%M%S")}'
    trade = {
        'id': trade_id,
        'producer': producer_name,
        'consumer': consumer_name,
        'watt_hours': watt_hours,
        'kwh': round(watt_hours / 1000, 2),
        'price_per_kwh': round(p2p_price, 2),
        'total_price': round(total_price, 2),
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'blockchain_tx': None,
        'sms_sent': 0
    }
    conn = get_db()
    conn.execute('''
        INSERT INTO trades (id, producer, consumer, watt_hours, kwh, price_per_kwh, total_price, status, created_at, blockchain_tx, sms_sent)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    ''', (trade_id, producer_name, consumer_name, watt_hours, trade['kwh'], trade['price_per_kwh'], trade['total_price'], 'pending', trade['created_at'], None, 0))
    conn.commit()
    conn.close()
    return trade

def simulate_sms(phone, message):
    print(f'[SMS] To: {phone} | Message: {message}')
    return True

def simulate_blockchain(trade_id, amount):
    tx_hash = f'0x{random.randint(10**15, 10**16-1):016x}'
    block = random.randint(100000, 200000)
    conn = get_db()
    conn.execute('''
        INSERT INTO blockchain (trade_id, tx_hash, block, amount, timestamp, status)
        VALUES (?,?,?,?,?,?)
    ''', (trade_id, tx_hash, block, amount, datetime.now().isoformat(), 'confirmed'))
    conn.commit()
    conn.close()
    return tx_hash, block

# ==============================
# Routes
# ==============================

@app.route('/')
def landing():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'producer':
            return redirect(url_for('producer_dashboard'))
        elif current_user.role == 'consumer':
            return redirect(url_for('consumer_dashboard'))
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('landing'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()
        conn.close()
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            login_user(User(user['id'], user['user_id'], user['email'], user['role']))
            return redirect(url_for('landing'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('landing'))
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        user_id = email.split('@')[0]
        conn = get_db()
        cur = conn.execute("SELECT COUNT(*) FROM users WHERE id = ?", (user_id,))
        if cur.fetchone()[0] == 0:
            conn.execute("INSERT INTO users (id, name, type, location, capacity, excess, phone, business) VALUES (?,?,?,?,?,?,?,?)",
                         (user_id, name, role, 'Enugu', '', '', '', ''))
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        conn.execute("INSERT INTO accounts (user_id, email, password_hash, role) VALUES (?,?,?,?)",
                     (user_id, email, hashed, role))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))

# ---------- Admin Dashboard ----------
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return "Access denied", 403
    return render_template('admin.html')

# ---------- Producer Dashboard ----------
@app.route('/producer')
@login_required
def producer_dashboard():
    if current_user.role != 'producer':
        return "Access denied", 403
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (current_user.user_id,)).fetchone()
    trades = conn.execute("SELECT * FROM trades WHERE producer = ? ORDER BY created_at DESC", (user['name'],)).fetchall()
    total_earnings = conn.execute("SELECT SUM(total_price) FROM trades WHERE producer = ? AND status='completed'", (user['name'],)).fetchone()[0] or 0
    conn.close()
    return render_template('producer.html', user=user, trades=trades, total_earnings=total_earnings)

# ---------- Consumer Dashboard ----------
@app.route('/consumer')
@login_required
def consumer_dashboard():
    if current_user.role != 'consumer':
        return "Access denied", 403
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (current_user.user_id,)).fetchone()
    trades = conn.execute("SELECT * FROM trades WHERE consumer = ? ORDER BY created_at DESC", (user['name'],)).fetchall()
    total_spent = conn.execute("SELECT SUM(total_price) FROM trades WHERE consumer = ? AND status='completed'", (user['name'],)).fetchone()[0] or 0
    conn.close()
    return render_template('consumer.html', user=user, trades=trades, total_spent=total_spent)

# ==============================
# API Routes
# ==============================

@app.route('/api/users')
@login_required
def get_users():
    conn = get_db()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    user_list = []
    for row in rows:
        lat, lng = get_user_location(row['id'])
        user_list.append({
            'id': row['id'],
            'name': row['name'],
            'type': row['type'],
            'location': row['location'],
            'lat': lat,
            'lng': lng,
            'details': dict(row)
        })
    return jsonify(user_list)

@app.route('/api/trades', methods=['GET'])
@login_required
def get_trades():
    conn = get_db()
    pending = conn.execute("SELECT * FROM trades WHERE status='pending' ORDER BY created_at DESC").fetchall()
    completed = conn.execute("SELECT * FROM trades WHERE status IN ('completed','failed') ORDER BY created_at DESC").fetchall()
    blockchain = conn.execute("SELECT * FROM blockchain ORDER BY timestamp DESC").fetchall()
    conn.close()
    all_trades = list(pending) + list(completed)
    stats = {
        'total_trades': len(all_trades),
        'completed_trades': len([t for t in completed if t['status'] == 'completed']),
        'pending_trades': len(pending),
        'total_revenue': sum([t['total_price'] for t in completed if t['status'] == 'completed'])
    }
    return jsonify({
        'pending': [dict(row) for row in pending],
        'completed': [dict(row) for row in completed],
        'stats': stats,
        'blockchain': [dict(row) for row in blockchain]
    })

@app.route('/api/trades', methods=['POST'])
@login_required
def new_trade():
    data = request.json
    producer_name = data.get('producer')
    consumer_name = data.get('consumer')
    watt_hours = float(data.get('watt_hours', 0))
    if not producer_name or not consumer_name or watt_hours <= 0:
        return jsonify({'error': 'Invalid data'}), 400
    trade = create_trade(producer_name, consumer_name, watt_hours)
    socketio.emit('new_trade', trade)
    return jsonify(trade)

@app.route('/api/trades/<trade_id>/validate', methods=['POST'])
@login_required
def validate_trade(trade_id):
    conn = get_db()
    trade = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    if not trade:
        conn.close()
        return jsonify({'error': 'Trade not found'}), 404
    
    delivered = random.random() < 0.75
    if delivered:
        conn.execute("UPDATE trades SET status = 'completed' WHERE id = ?", (trade_id,))
        conn.commit()
        total = trade['total_price']
        producer_payout = round(total * 0.85, 2)
        disco_fee = round(total * 0.10, 2)
        platform_fee = round(total * 0.05, 2)
        tx_hash, block = simulate_blockchain(trade_id, total)
        conn.execute("UPDATE trades SET blockchain_tx = ? WHERE id = ?", (tx_hash, trade_id))
        conn.commit()
        producer_phone = conn.execute("SELECT phone FROM users WHERE name = ?", (trade['producer'],)).fetchone()
        consumer_phone = conn.execute("SELECT phone FROM users WHERE name = ?", (trade['consumer'],)).fetchone()
        if producer_phone and producer_phone['phone']:
            simulate_sms(producer_phone['phone'], f'✅ Trade {trade_id} completed! You earned ₦{producer_payout}. TX: {tx_hash[:8]}...')
        if consumer_phone and consumer_phone['phone']:
            simulate_sms(consumer_phone['phone'], f'✅ Trade {trade_id} successful. You paid ₦{total}. Power delivered.')
        conn.close()
        return jsonify({
            'status': 'completed',
            'producer_payout': producer_payout,
            'disco_fee': disco_fee,
            'platform_fee': platform_fee,
            'tx_hash': tx_hash,
            'block': block
        })
    else:
        conn.execute("UPDATE trades SET status = 'failed' WHERE id = ?", (trade_id,))
        conn.commit()
        consumer_phone = conn.execute("SELECT phone FROM users WHERE name = ?", (trade['consumer'],)).fetchone()
        if consumer_phone and consumer_phone['phone']:
            simulate_sms(consumer_phone['phone'], f'❌ Trade {trade_id} failed. Refund of ₦{trade["total_price"]} processed.')
        conn.close()
        return jsonify({'status': 'failed'})

# ---------- NEW: Reject Endpoint ----------
@app.route('/api/trades/<trade_id>/reject', methods=['POST'])
@login_required
def reject_trade(trade_id):
    conn = get_db()
    trade = conn.execute("SELECT * FROM trades WHERE id = ? AND status='pending'", (trade_id,)).fetchone()
    if not trade:
        conn.close()
        return jsonify({'error': 'Trade not found or already processed'}), 404

    conn.execute("UPDATE trades SET status='failed' WHERE id = ?", (trade_id,))
    conn.commit()
    
    consumer_phone = conn.execute("SELECT phone FROM users WHERE name = ?", (trade['consumer'],)).fetchone()
    if consumer_phone and consumer_phone['phone']:
        simulate_sms(consumer_phone['phone'], f'❌ Trade {trade_id} rejected by producer. Refund of ₦{trade["total_price"]} processed.')
    
    conn.close()
    return jsonify({'status': 'rejected'})

@app.route('/api/stats')
@login_required
def get_stats():
    conn = get_db()
    completed = conn.execute("SELECT * FROM trades WHERE status='completed'").fetchall()
    conn.close()
    now = datetime.now()
    daily_revenue = []
    daily_energy = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        day_trades = [t for t in completed if t['created_at'].startswith(day_str)]
        revenue = sum([t['total_price'] for t in day_trades]) if day_trades else random.randint(200, 3000)
        energy = sum([t['kwh'] for t in day_trades]) if day_trades else random.randint(2, 20)
        daily_revenue.append({'date': day_str, 'revenue': round(revenue, 2)})
        daily_energy.append({'date': day_str, 'kwh': round(energy, 1)})
    return jsonify({
        'daily_revenue': daily_revenue,
        'daily_energy': daily_energy,
        'total_revenue': sum([t['total_price'] for t in completed]),
        'total_energy': sum([t['kwh'] for t in completed])
    })

@app.route('/api/predictions')
@login_required
def get_predictions():
    conn = get_db()
    completed = conn.execute("SELECT * FROM trades WHERE status='completed'").fetchall()
    conn.close()
    if len(completed) < 3:
        predictions = []
        for i in range(1, 8):
            pred = {
                'date': (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d'),
                'predicted_revenue': round(random.uniform(1000, 5000), 2),
                'predicted_energy': round(random.uniform(10, 40), 1)
            }
            predictions.append(pred)
        return jsonify(predictions)
    avg_revenue = sum([t['total_price'] for t in completed]) / len(completed)
    avg_energy = sum([t['kwh'] for t in completed]) / len(completed)
    predictions = []
    for i in range(1, 8):
        pred = {
            'date': (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d'),
            'predicted_revenue': round(avg_revenue * (1 + random.uniform(-0.2, 0.2)), 2),
            'predicted_energy': round(avg_energy * (1 + random.uniform(-0.2, 0.2)), 1)
        }
        predictions.append(pred)
    return jsonify(predictions)

@app.route('/api/anomalies')
@login_required
def get_anomalies():
    conn = get_db()
    all_trades = conn.execute("SELECT * FROM trades").fetchall()
    conn.close()
    anomalies = []
    for trade in all_trades:
        if trade['kwh'] > 10:
            anomalies.append({
                'trade_id': trade['id'],
                'type': 'large_trade',
                'message': f'Unusually large trade: {trade["kwh"]}kWh',
                'severity': 'warning'
            })
        producer_failures = [t for t in all_trades if t['producer'] == trade['producer'] and t['status'] == 'failed']
        if len(producer_failures) > 2:
            anomalies.append({
                'trade_id': trade['id'],
                'type': 'producer_failures',
                'message': f'Producer {trade["producer"]} has {len(producer_failures)} failed trades',
                'severity': 'high'
            })
    return jsonify(anomalies[:10])

# ---------- AI Chat API ----------
@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    data = request.json
    message = data.get('message', '').lower()
    user_id = current_user.user_id

    conn = get_db()
    user = conn.execute("SELECT name, type FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not user:
        return jsonify({'response': "❌ User not found."})

    if 'buy' in message and 'kwh' in message:
        match = re.search(r'buy\s+(\d+\.?\d*)\s*kwh\s+from\s+([\w\s]+)', message)
        if match:
            amount = float(match.group(1))
            producer_name = match.group(2).strip()
            conn = get_db()
            producer = conn.execute("SELECT name FROM users WHERE name LIKE ? AND type='producer'", (f'%{producer_name}%',)).fetchone()
            if producer:
                trade = create_trade(producer['name'], user['name'], amount * 1000)
                conn.close()
                return jsonify({'response': f"✅ Trade created! You bought {amount} kWh from {producer['name']} for ₦{trade['total_price']}. Trade ID: {trade['id']}"})
            else:
                return jsonify({'response': "❌ Producer not found. Please check the name."})
        else:
            return jsonify({'response': "⚠️ Please say: 'buy [amount] kWh from [producer name]'"})

    elif 'balance' in message or 'spent' in message:
        conn = get_db()
        total = conn.execute("SELECT SUM(total_price) FROM trades WHERE consumer = ? AND status='completed'", (user['name'],)).fetchone()[0] or 0
        conn.close()
        return jsonify({'response': f"💰 Your total spending: ₦{total:.2f}"})

    elif 'history' in message or 'trades' in message:
        conn = get_db()
        trades = conn.execute("SELECT * FROM trades WHERE consumer = ? OR producer = ? ORDER BY created_at DESC LIMIT 5", (user['name'], user['name'])).fetchall()
        conn.close()
        if trades:
            lines = []
            for t in trades:
                lines.append(f"{t['created_at'][:10]} – {t['producer']} → {t['consumer']} ({t['kwh']} kWh, ₦{t['total_price']}) – {t['status']}")
            return jsonify({'response': "📋 Recent trades:\n" + "\n".join(lines)})
        else:
            return jsonify({'response': "📭 No trades yet."})

    elif 'help' in message:
        return jsonify({'response': "🤖 I can help you:\n- Buy power: 'buy 3 kWh from Mr. Ade'\n- Check balance: 'balance'\n- View history: 'history'\n- Get help: 'help'"})
    else:
        return jsonify({'response': "🤖 I'm your energy assistant. Try: 'buy 3 kWh from Mr. Ade' or 'help'."})

# ==============================
# Main
# ==============================
if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
