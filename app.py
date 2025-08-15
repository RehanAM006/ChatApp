from flask import Flask, render_template, request, abort
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize Flask first
app = Flask(__name__)
app.config['SECRET_KEY'] = 'devkey'  # change in production

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Init DB and SocketIO
db = SQLAlchemy(app)
socketio = SocketIO(app)

# ---- IP -> Username binding (EDIT THESE) ----
AUTHORIZED_USERS = {
    "x.x.xx.0": "Rehan",     # Windows
    "x.x.xx..x.12": "Rehan",
    "1x.x.x..x22": "MintVM",    # Mint VM
    "1x.x..xx.12":  "Rehan",    # Other device
    "x.x.x.x..x.4": "Rehan"
    # Add more IPs if needed...
}

ALLOW_LOOPBACK = True

# ----- Models -----
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ----- Utility -----
def resolve_username(ip: str) -> str | None:
    if ALLOW_LOOPBACK and ip == "127.0.0.1":
        return "LocalDev"
    return AUTHORIZED_USERS.get(ip)

def ts():
    return datetime.now().strftime("%H:%M:%S")

@app.before_request
def ip_gate():
    ip = request.remote_addr
    user = resolve_username(ip)
    if not user:
        app.logger.warning(f"DENY {ip} (not in AUTHORIZED_USERS)")
        abort(403)

# ----- Routes -----
@app.route("/")
def home():
    ip = request.remote_addr
    username = resolve_username(ip)
    return render_template("index.html", username=username)

# ----- Socket Events -----
@socketio.on("connect")
def on_connect():
    ip = request.remote_addr
    user = resolve_username(ip)
    if not user:
        return False  # reject socket

    join_room("family")

    # Send last 50 messages
    last_messages = Message.query.order_by(Message.timestamp.desc()).limit(50).all()
    for msg in reversed(last_messages):
        emit("message", {"from": msg.username, "text": msg.text, "time": msg.timestamp.strftime("%H:%M:%S")})

    emit("system", {"msg": f"{user} joined", "time": ts()}, room="family")

@socketio.on("send_message")
def on_send_message(data):
    ip = request.remote_addr
    user = resolve_username(ip)
    if not user:
        return False

    text = (data or {}).get("text", "").strip()
    if not text:
        return

    # Save to DB
    new_msg = Message(username=user, text=text)
    db.session.add(new_msg)
    db.session.commit()

    # Broadcast to all
    emit("message", {"from": user, "text": text, "time": ts()}, room="family")

# ----- Run -----
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)

