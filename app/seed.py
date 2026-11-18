from sqlalchemy.orm import Session
from .models import User
from .auth import hash_password

def seed_staff(db: Session):
    # Only staff demo accounts are seeded. Student accounts are created from real OULAD IDs.
    if not db.query(User).filter(User.role == "teacher").first():
        db.add(User(name="Aarav Mehta", email="teacher@campus.edu",
                    password_hash=hash_password("Teacher@123"), role="teacher",
                    department="Academic Faculty"))
    if not db.query(User).filter(User.role == "admin").first():
        db.add(User(name="Priya Sharma", email="admin@campus.edu",
                    password_hash=hash_password("Admin@123"), role="admin",
                    department="Administration"))
    db.commit()
