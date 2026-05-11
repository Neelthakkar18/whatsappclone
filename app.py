from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-12345'

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Create upload folders
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/profile_photos', exist_ok=True)
os.makedirs('static', exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    profile_photo = db.Column(db.String(200), default='/static/default-avatar.png')
    bio = db.Column(db.String(160), default='Hey there! I am using WhatsApp Clone')
    online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.now)

# Message Model
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    is_read = db.Column(db.Boolean, default=False)

# Blocked Users Model
class BlockedUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    blocked_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def is_blocked(user1_id, user2_id):
    block = BlockedUser.query.filter_by(blocker_id=user1_id, blocked_id=user2_id).first()
    return block is not None

def is_blocked_by_other(user1_id, user2_id):
    block = BlockedUser.query.filter_by(blocker_id=user2_id, blocked_id=user1_id).first()
    return block is not None

# Routes
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
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            user.online = True
            db.session.commit()
            return redirect("/chat")
        return render_template("login.html", error="Invalid credentials")
    
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect("/chat")
    
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template("register.html", error="Username already exists")
        
        hashed = generate_password_hash(password)
        user = User(username=username, password=hashed)
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
    user.last_seen = datetime.now()
    db.session.commit()
    logout_user()
    return redirect("/login")

@app.route("/chat")
@login_required
def chat():
    users = User.query.filter(User.id != current_user.id).all()
    visible_users = []
    for user in users:
        if not is_blocked(current_user.id, user.id):
            visible_users.append(user)
    return render_template("chat.html", users=visible_users)

@app.route("/get_messages/<int:user_id>")
@login_required
def get_messages(user_id):
    if is_blocked_by_other(current_user.id, user_id):
        return jsonify({'error': 'You have been blocked by this user', 'blocked_by_other': True}), 403
    
    if is_blocked(current_user.id, user_id):
        return jsonify({'error': 'You have blocked this user', 'blocked_by_you': True}), 403
    
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()
    
    for msg in messages:
        if msg.receiver_id == current_user.id and not msg.is_read:
            msg.is_read = True
            db.session.commit()
    
    return jsonify([{
        'id': msg.id,
        'text': msg.text,
        'sender_id': msg.sender_id,
        'receiver_id': msg.receiver_id,
        'timestamp': msg.timestamp.isoformat(),
        'is_read': msg.is_read
    } for msg in messages])

@app.route("/search_users")
@login_required
def search_users():
    query = request.args.get('q', '')
    if len(query) < 1:
        return jsonify([])
    
    users = User.query.filter(
        User.id != current_user.id,
        User.username.contains(query)
    ).limit(20).all()
    
    result = []
    for user in users:
        if not is_blocked(current_user.id, user.id) and not is_blocked_by_other(current_user.id, user.id):
            result.append({
                'id': user.id,
                'username': user.username,
                'profile_photo': user.profile_photo,
                'online': user.online,
                'bio': user.bio
            })
    
    return jsonify(result)

@app.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    bio = request.form.get('bio')
    if bio:
        current_user.bio = bio
    
    profile_photo = request.files.get('profile_photo')
    if profile_photo and profile_photo.filename:
        filename = secure_filename(f"{current_user.id}_{datetime.now().timestamp()}_{profile_photo.filename}")
        filepath = os.path.join('static/profile_photos', filename)
        profile_photo.save(filepath)
        current_user.profile_photo = f'/static/profile_photos/{filename}'
    
    db.session.commit()
    return jsonify({'success': True})

@app.route("/get_user_profile/<int:user_id>")
@login_required
def get_user_profile(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'profile_photo': user.profile_photo,
        'bio': user.bio,
        'online': user.online,
        'last_seen': user.last_seen.isoformat() if user.last_seen else None
    })

@app.route("/block_user/<int:user_id>", methods=["POST"])
@login_required
def block_user(user_id):
    if current_user.id == user_id:
        return jsonify({'error': 'Cannot block yourself'}), 400
    
    existing = BlockedUser.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    if existing:
        return jsonify({'error': 'Already blocked'}), 400
    
    block = BlockedUser(blocker_id=current_user.id, blocked_id=user_id)
    db.session.add(block)
    db.session.commit()
    return jsonify({'success': True})

@app.route("/unblock_user/<int:user_id>", methods=["POST"])
@login_required
def unblock_user(user_id):
    block = BlockedUser.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    if block:
        db.session.delete(block)
        db.session.commit()
    return jsonify({'success': True})

@app.route("/get_blocked_users")
@login_required
def get_blocked_users():
    blocks = BlockedUser.query.filter_by(blocker_id=current_user.id).all()
    users = []
    for block in blocks:
        user = User.query.get(block.blocked_id)
        if user:
            users.append({
                'id': user.id,
                'username': user.username,
                'profile_photo': user.profile_photo
            })
    return jsonify(users)

@app.route("/upload_media", methods=["POST"])
@login_required
def upload_media():
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file provided'}), 400
    
    filename = secure_filename(f"{current_user.id}_{datetime.now().timestamp()}_{file.filename}")
    filepath = os.path.join('static/uploads', filename)
    file.save(filepath)
    
    file_type = 'image' if file.content_type.startswith('image/') else 'video' if file.content_type.startswith('video/') else 'document'
    media_url = f'/static/uploads/{filename}'
    
    return jsonify({'media_url': media_url, 'file_type': file_type})

# Socket.IO Events
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(str(current_user.id))
        current_user.online = True
        db.session.commit()
        emit('user_status', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        current_user.online = False
        current_user.last_seen = datetime.now()
        db.session.commit()
        emit('user_status', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True)

@socketio.on('send_message')
def handle_send_message(data):
    receiver_id = int(data['receiver'])
    text = data['message']
    
    # Check blocks
    if is_blocked_by_other(current_user.id, receiver_id):
        emit('error', {'message': 'You have been blocked by this user'}, room=str(current_user.id))
        return
    
    if is_blocked(current_user.id, receiver_id):
        emit('error', {'message': 'You have blocked this user'}, room=str(current_user.id))
        return
    
    # Save message
    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        text=text
    )
    db.session.add(message)
    db.session.commit()
    
    message_data = {
        'id': message.id,
        'message': message.text,
        'sender_id': message.sender_id,
        'sender_name': current_user.username,
        'timestamp': message.timestamp.isoformat()
    }
    
    # Send to receiver
    emit('receive_message', message_data, room=str(receiver_id))
    # Send confirmation to sender
    emit('message_sent', message_data, room=str(current_user.id))

@socketio.on('typing')
def handle_typing(data):
    receiver_id = data['receiver_id']
    emit('user_typing', {'sender_id': current_user.id, 'username': current_user.username}, room=str(receiver_id))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("✅ Database created!")
    
    socketio.run(app, debug=True, port=8000)
