from flask import Flask, render_template, request, redirect, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, login_manager, socketio
from models import User, Message, BlockedUser

from flask_socketio import emit, join_room

import os

app = Flask(__name__)

app.config['SECRET_KEY'] = 'secret'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager.init_app(app)
socketio.init_app(app)

# ================= DATABASE =================

with app.app_context():
    db.create_all()

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

# ================= ROUTES =================

@app.route("/")
def index():

    if current_user.is_authenticated:
        return redirect("/chat")

    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")

        password = request.form.get("password")

        user = User.query.filter_by(
            username=username
        ).first()

        if user and check_password_hash(
            user.password,
            password
        ):

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

    if request.method == "POST":

        username = request.form.get("username")

        password = request.form.get("password")

        existing = User.query.filter_by(
            username=username
        ).first()

        if existing:

            return render_template(
                "register.html",
                error="Username already exists"
            )

        user = User(
            username=username,
            password=generate_password_hash(password)
        )

        db.session.add(user)

        db.session.commit()

        login_user(user)

        return redirect("/chat")

    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():

    current_user.online = False

    db.session.commit()

    logout_user()

    return redirect("/login")

@app.route("/chat")
@login_required
def chat():

    users = User.query.filter(
        User.id != current_user.id
    ).all()

    return render_template(
        "chat.html",
        users=users
    )

# ================= SOCKET =================

@socketio.on("connect")
def handle_connect():

    if current_user.is_authenticated:

        join_room(str(current_user.id))

@socketio.on("send_message")
def handle_send_message(data):

    receiver_id = int(data["receiver"])

    text = data["message"]

    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        text=text,
        is_delivered=True
    )

    db.session.add(message)

    db.session.commit()

    message_data = {
        "id": message.id,
        "text": message.text,
        "sender_id": message.sender_id,
        "receiver_id": message.receiver_id,
        "timestamp": message.timestamp.isoformat(),
        "edited": False,
        "deleted": False
    }

    emit(
        "receive_message",
        message_data,
        room=str(receiver_id)
    )

    emit(
        "receive_message",
        message_data,
        room=str(current_user.id)
    )

# ================= EDIT MESSAGE =================

@socketio.on("edit_message")
def handle_edit_message(data):

    message = Message.query.get(
        data["message_id"]
    )

    if not message:
        return

    if message.sender_id != current_user.id:
        return

    message.text = data["new_text"]

    message.edited = True

    db.session.commit()

    emit(
        "message_edited",
        {
            "message_id": message.id,
            "new_text": message.text,
            "edited": True
        },
        room=str(message.receiver_id)
    )

    emit(
        "message_edited",
        {
            "message_id": message.id,
            "new_text": message.text,
            "edited": True
        },
        room=str(message.sender_id)
    )

# ================= DELETE MESSAGE =================

@socketio.on("delete_message")
def handle_delete_message(data):

    message = Message.query.get(
        data["message_id"]
    )

    if not message:
        return

    if message.sender_id != current_user.id:
        return

    message.deleted = True

    message.text = "🚫 This message was deleted"

    db.session.commit()

    emit(
        "message_deleted",
        {
            "message_id": message.id,
            "text": message.text
        },
        room=str(message.receiver_id)
    )

    emit(
        "message_deleted",
        {
            "message_id": message.id,
            "text": message.text
        },
        room=str(message.sender_id)
    )

# ================= RUN =================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=False
    )
