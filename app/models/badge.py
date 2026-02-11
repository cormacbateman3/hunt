from sqlalchemy import JSON

from app.extensions import db


class Badge(db.Model):
    __tablename__ = "badges"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon_url = db.Column(db.String(500))
    criteria = db.Column(JSON, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class UserBadge(db.Model):
    __tablename__ = "user_badges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    badge_id = db.Column(db.Integer, db.ForeignKey("badges.id"), nullable=False, index=True)
    earned_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
