from sqlalchemy.orm import relationship

from app.extensions import db


class Listing(db.Model):
    __tablename__ = "listings"

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    license_year = db.Column(db.SmallInteger, nullable=False, index=True)
    license_type = db.Column(db.String(50), nullable=False, index=True)
    county = db.Column(db.String(50), nullable=False, index=True)
    condition_grade = db.Column(db.String(20), nullable=False)
    listing_type = db.Column(db.String(10), nullable=False)
    starting_price = db.Column(db.Numeric(10, 2), nullable=False)
    reserve_price = db.Column(db.Numeric(10, 2))
    buy_now_price = db.Column(db.Numeric(10, 2))
    current_bid = db.Column(db.Numeric(10, 2))
    bid_count = db.Column(db.Integer, default=0, nullable=False)
    auction_end = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="draft", nullable=False, index=True)
    views = db.Column(db.Integer, default=0, nullable=False)
    featured = db.Column(db.Boolean, default=False, nullable=False)
    condition_notes = db.Column(db.Text)
    provenance = db.Column(db.Text)
    shipping_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    seller = relationship("User", back_populates="listings")
    images = relationship("ListingImage", back_populates="listing", cascade="all, delete-orphan")
    bids = relationship("Bid", back_populates="listing", cascade="all, delete-orphan")


class ListingImage(db.Model):
    __tablename__ = "listing_images"

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False, index=True)
    s3_key = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(1000), nullable=False)
    thumbnail_url = db.Column(db.String(1000), nullable=False)
    sort_order = db.Column(db.SmallInteger, default=0, nullable=False)
    caption = db.Column(db.String(300))
    uploaded_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    listing = relationship("Listing", back_populates="images")
