from sqlalchemy.orm import relationship

from app.extensions import db


class Bid(db.Model):
    __tablename__ = "bids"

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False, index=True)
    bidder_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    proxy_max = db.Column(db.Numeric(10, 2))
    is_auto = db.Column(db.Boolean, default=False, nullable=False)
    is_winning = db.Column(db.Boolean, default=False, nullable=False)
    placed_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    listing = relationship("Listing", back_populates="bids")
    bidder = relationship("User", back_populates="bids")
