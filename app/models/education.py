from app.extensions import db


class EducationArticle(db.Model):
    __tablename__ = "education_articles"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    era_start = db.Column(db.SmallInteger)
    era_end = db.Column(db.SmallInteger)
    county = db.Column(db.String(50), index=True)
    cover_image_url = db.Column(db.String(1000))
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    published_at = db.Column(db.DateTime)
