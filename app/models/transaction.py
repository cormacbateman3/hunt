from app.extensions import db


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listings.id"), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    sale_amount = db.Column(db.Numeric(10, 2), nullable=False)
    platform_fee = db.Column(db.Numeric(10, 2), nullable=False)
    stripe_payment_id = db.Column(db.String(200))
    stripe_transfer_id = db.Column(db.String(200))
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    tracking_number = db.Column(db.String(100))
    buyer_confirmed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
