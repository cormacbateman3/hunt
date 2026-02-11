from app.extensions import db


class Collection(db.Model):
    __tablename__ = "collections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    license_year = db.Column(db.SmallInteger, nullable=False, index=True)
    county = db.Column(db.String(50), nullable=False, index=True)
    license_type = db.Column(db.String(50), nullable=False)
    condition_grade = db.Column(db.String(20))
    notes = db.Column(db.Text)
    image_url = db.Column(db.String(1000))
    acquired_via = db.Column(db.String(20))
    acquired_at = db.Column(db.Date)
    is_public = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
