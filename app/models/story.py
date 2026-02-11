from app.extensions import db


class UserStory(db.Model):
    __tablename__ = "user_stories"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="draft", nullable=False, index=True)
    related_county = db.Column(db.String(50), index=True)
    related_year = db.Column(db.SmallInteger, index=True)
    cover_image_url = db.Column(db.String(1000))
    submitted_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
