"""User model for authentication."""

from datetime import datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask_login import UserMixin

from ..extensions import db, login_manager

ph = PasswordHasher()


class User(UserMixin, db.Model):
    """User account model."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to games
    games = db.relationship("GameRecord", backref="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        """Hash and store password using argon2."""
        self.password_hash = ph.hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        try:
            ph.verify(self.password_hash, password)
            # Rehash if parameters have changed
            if ph.check_needs_rehash(self.password_hash):
                self.password_hash = ph.hash(password)
            return True
        except VerifyMismatchError:
            return False

    def __repr__(self) -> str:
        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """Load user by ID for Flask-Login."""
    return db.session.get(User, int(user_id))
