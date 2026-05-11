from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from zoneinfo import ZoneInfo
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here-12345')

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')

if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Create folders
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/profile_photos', exist_ok=True)
os.makedirs('static', exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ================= USER MODEL =================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(120),
        nullable=False
    )

    profile_photo = db.Column(
        db.String(200),
        default='/static/default-avatar.png'
    )

    bio = db.Column(
        db.String(160),
        default='Hey there! I am using WhatsApp Clone'
    )

    online = db.Column(
        db.Boolean,
        default=False
    )

    last_seen = db.Column(
        db.DateTime,
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata"))
    )

# ================= MESSAGE MODEL =================

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    receiver_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    text = db.Column(
        db.Text,
        nullable=True
    )

    message_type = db.Column(
        db.String(20),
        default='text'
    )

    media_url = db.Column(
        db.String(500),
        nullable=True
    )

    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata"))
    )

    is_read = db.Column(
        db.Boolean,
        default=False
    )

    is_delivered = db.Column(
        db.Boolean,
        default=False
    )

# ================= BLOCK MODEL =================

class BlockedUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    blocker_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    blocked_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata"))
    )

# ================= LOGIN =================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ================= BLOCK CHECK =================

def is_blocked(user1_id, user2_id):
    block = BlockedUser.query.filter_by(
        blocker_id=user1_id,
        blocked_id=user2_id
    ).first()

    return block is not None

def is_blocked_by_other(user1_id, user2_id):
    block = BlockedUser.query.filter_by(
        blocker_id=user2_id,
        blocked_id=user1_id
    ).first()

    return block is not None

# ================= ROUTES =================

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect("/chat")

    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect("/chat")

    if request.method == "POST":

        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(
            username=username
        ).first()

        if user and check_password_hash(user.password, password):

            login_user(user)

            user.online = True

            db.session.commit()

            return redirect("/chat")

        return render_template(
            "login.html",
            error="Invalid credentials"
        )

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect("/chat")

    if request.method == "POST":

        username = request.form.get('username')
        password = request.form.get('password')

        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user:
            return render_template(
                "register.html",
                error="Username already exists"
            )

        hashed = generate_password_hash(password)

        user = User(
            username=username,
            password=hashed
        )

        db.session.add(user)
        db.session.commit()

        login_user(user)

        return redirect("/chat")

    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():

    user = User.query.get(current_user.id)

    user.online = False

    user.last_seen = datetime.now(
        ZoneInfo("Asia/Kolkata")
    )

    db.session.commit()

    logout_user()

    return redirect("/login")

@app.route("/chat")
@login_required
def chat():

    users = User.query.filter(
        User.id != current_user.id
    ).all()

    visible_users = []

    for user in users:
        if not is_blocked(current_user.id, user.id):
            visible_users.append(user)

    return render_template(
        "chat.html",
        users=visible_users
    )

# ================= SOCKET =================

@socketio.on('connect')
def handle_connect():

    if current_user.is_authenticated:

        join_room(str(current_user.id))

        current_user.online = True

        db.session.commit()

        emit('user_status', {
            'user_id': current_user.id,
            'username': current_user.username,
            'status': 'online'
        }, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():

    if current_user.is_authenticated:

        current_user.online = False

        current_user.last_seen = datetime.now(
            ZoneInfo("Asia/Kolkata")
        )

        db.session.commit()

        emit('user_status', {
            'user_id': current_user.id,
            'username': current_user.username,
            'status': 'offline'
        }, broadcast=True)

@socketio.on('send_message')
def handle_send_message(data):

    receiver_id = int(data['receiver_id'])

    text = data.get('text', '')

    message_type = data.get('message_type', 'text')

    media_url = data.get('media_url', '')

    if is_blocked_by_other(current_user.id, receiver_id):

        emit('error', {
            'message': 'You have been blocked'
        }, room=str(current_user.id))

        return

    if is_blocked(current_user.id, receiver_id):

        emit('error', {
            'message': 'You blocked this user'
        }, room=str(current_user.id))

        return

    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        text=text,
        message_type=message_type,
        media_url=media_url if media_url else None,
        is_delivered=True
    )

    db.session.add(message)
    db.session.commit()

    message_data = {
        'id': message.id,
        'text': message.text,
        'message_type': message.message_type,
        'media_url': message.media_url,
        'sender_id': message.sender_id,
        'receiver_id': message.receiver_id,
        'sender_name': current_user.username,
        'timestamp': message.timestamp.isoformat(),
        'is_read': message.is_read,
        'is_delivered': message.is_delivered
    }

    emit(
        'new_message',
        message_data,
        room=str(receiver_id)
    )

    emit(
        'message_sent',
        message_data,
        room=str(current_user.id)
    )

# ================= DATABASE =================

with app.app_context():
    db.create_all()
    print("✅ Database tables created successfully!")

# ================= RUN =================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 8000))

    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False
    )
