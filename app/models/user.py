from flask_login import UserMixin
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(100))
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(500))
    county = db.Column(db.String(50))
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    seller_rating = db.Column(db.Numeric(3, 2))
    buyer_rating = db.Column(db.Numeric(3, 2))
    notification_prefs = db.Column(JSON)
    stripe_customer_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    last_login = db.Column(db.DateTime)

    listings = relationship("Listing", back_populates="seller", lazy="dynamic")
    bids = relationship("Bid", back_populates="bidder", lazy="dynamic")
