from extensions import db
from flask_login import UserMixin
from datetime import datetime
from zoneinfo import ZoneInfo

# ================= USER MODEL =================

class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(200),
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
        default=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        )
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
        db.Text
    )

    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        )
    )

    is_read = db.Column(
        db.Boolean,
        default=False
    )

    is_delivered = db.Column(
        db.Boolean,
        default=False
    )

    edited = db.Column(
        db.Boolean,
        default=False
    )

    deleted = db.Column(
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
