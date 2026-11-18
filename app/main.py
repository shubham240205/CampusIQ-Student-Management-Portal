from datetime import date
from math import ceil
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, desc, or_
from .database import Base, engine, get_db
from .models import User, Subject, Registration, Assessment, AssessmentResult, Engagement, Attendance, ClassSession
from .auth import verify_password, create_token, current_user, require_roles
from .seed import seed_staff

Base.metadata.create_all(bind=engine)
with next(get_db()) as session:
    seed_staff(session)

app = FastAPI(title="CampusIQ Student Management Portal", version="2.1.0",
              description="OULAD-powered academic analytics and student progress portal.")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def home():
    return FileResponse("app/static/index.html", headers={"Cache-Control": "no-store"})

@app.post("/api/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username.lower()).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"access_token": create_token(user), "token_type": "bearer",
            "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role}}

@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "roll_no": user.roll_no, "department": user.department, "semester": user.semester,
            "oulad_student_id": user.oulad_student_id}

# Aggregate once in SQL instead of running multiple queries for every student.
def student_aggregate_query(db: Session):
    marks = (db.query(AssessmentResult.student_id.label("student_id"),
                      func.avg(AssessmentResult.score).label("average_marks"),
                      func.count(AssessmentResult.id).label("assessment_count"))
             .filter(AssessmentResult.score.isnot(None))
             .group_by(AssessmentResult.student_id).subquery())
    engagement = (db.query(Engagement.student_id.label("student_id"),
                           func.coalesce(func.sum(Engagement.total_clicks), 0).label("clicks"),
                           func.coalesce(func.sum(Engagement.active_days), 0).label("active_days"))
                  .group_by(Engagement.student_id).subquery())
    attendance = (db.query(Attendance.student_id.label("student_id"),
                           func.count(Attendance.id).label("sessions"),
                           func.coalesce(func.sum(case((Attendance.present.is_(True), 1), else_=0)), 0).label("present"))
                 .group_by(Attendance.student_id).subquery())
    return marks, engagement, attendance

def risk_label(avg, clicks, attendance_pct):
    if (avg is not None and avg < 40) or (attendance_pct is not None and attendance_pct < 75):
        return "At Risk"
    if (avg is not None and avg < 50) or (avg is not None and clicks < 20):
        return "Needs Attention"
    return "On Track"

def student_detail_data(db: Session, student: User):
    results = (db.query(AssessmentResult, Assessment, Subject)
        .join(Assessment, AssessmentResult.assessment_id == Assessment.id)
        .join(Subject, Assessment.subject_id == Subject.id)
        .filter(AssessmentResult.student_id == student.id)
        .order_by(Assessment.date.asc().nullslast(), AssessmentResult.id.asc()).all())
    valid = [(r, a, s) for r, a, s in results if r.score is not None]
    average = round(sum(float(r.score) for r, _, _ in valid) / len(valid), 1) if valid else None
    clicks, active_days = db.query(
        func.coalesce(func.sum(Engagement.total_clicks), 0),
        func.coalesce(func.sum(Engagement.active_days), 0)
    ).filter(Engagement.student_id == student.id).one()
    total, present = db.query(
        func.count(Attendance.id),
        func.coalesce(func.sum(case((Attendance.present.is_(True), 1), else_=0)), 0)
    ).filter(Attendance.student_id == student.id).one()
    attendance_pct = round((present / total) * 100, 1) if total else None

    by_subject = {}
    marks = []
    for result, assessment, subject in valid:
        marks.append({"subject": subject.name, "code": subject.code,
                      "assessment": assessment.assessment_type or "Assessment",
                      "score": float(result.score), "max_score": 100,
                      "weight": float(assessment.weight or 0),
                      "assessment_date": assessment.date})
        item = by_subject.setdefault(subject.id, {"subject": subject.name, "code": subject.code, "scores": []})
        item["scores"].append(float(result.score))
    subject_performance = [{"subject": x["subject"], "code": x["code"],
                            "average": round(sum(x["scores"]) / len(x["scores"]), 1),
                            "assessment_count": len(x["scores"])} for x in by_subject.values()]

    attendance_rows = (db.query(Subject.name, Subject.code, func.count(Attendance.id),
                        func.coalesce(func.sum(case((Attendance.present.is_(True), 1), else_=0)), 0))
        .join(Attendance, Attendance.subject_id == Subject.id)
        .filter(Attendance.student_id == student.id)
        .group_by(Subject.name, Subject.code).all())
    attendance_by_subject = [{"subject": name, "code": code, "total": total,
                              "present": present, "percentage": round(present / total * 100, 1)}
                             for name, code, total, present in attendance_rows]
    registered_subjects = (db.query(Subject).join(Registration, Registration.subject_id == Subject.id)
                           .filter(Registration.student_id == student.id)
                           .order_by(Subject.code).all())
    return {"id": student.id, "name": student.name, "roll_no": student.roll_no,
            "email": student.email, "department": student.department, "semester": student.semester,
            "oulad_student_id": student.oulad_student_id, "average_marks": average,
            "attendance": attendance_pct, "engagement_clicks": int(clicks or 0),
            "active_days": int(active_days or 0), "assessment_count": len(marks),
            "marks": marks, "subject_performance": subject_performance,
            "attendance_by_subject": attendance_by_subject,
            "registered_subjects": [{"id": s.id, "code": s.code, "name": s.name} for s in registered_subjects],
            "academic_standing": risk_label(average, int(clicks or 0), attendance_pct)}

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    # Exercise the DB connection so this endpoint reports real database health.
    db.execute(func.now())
    return {"status": "healthy", "service": "campusiq-oulad", "database": "connected"}

@app.get("/api/diagnostics/data")
def data_diagnostics(db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    return {
        "students": db.query(func.count(User.id)).filter(User.role == "student", User.active.is_(True)).scalar() or 0,
        "subjects": db.query(func.count(Subject.id)).scalar() or 0,
        "registrations": db.query(func.count(Registration.id)).scalar() or 0,
        "assessment_definitions": db.query(func.count(Assessment.id)).scalar() or 0,
        "assessment_results": db.query(func.count(AssessmentResult.id)).scalar() or 0,
        "engagement_summaries": db.query(func.count(Engagement.id)).scalar() or 0,
        "attendance_records": db.query(func.count(Attendance.id)).scalar() or 0,
    }

@app.get("/api/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == "student":
        data = student_detail_data(db, user)
        return {"students": 1, "average_marks": data["average_marks"],
                "attendance": data["attendance"], "engagement_clicks": data["engagement_clicks"],
                "active_days": data["active_days"], "assessment_count": data["assessment_count"],
                "at_risk": int(data["academic_standing"] == "At Risk"),
                "subject_count": len(data["registered_subjects"]),
                "subject_performance": data["subject_performance"],
                "academic_standing": data["academic_standing"]}

    marks, engagement, attendance = student_aggregate_query(db)
    q = (db.query(User.id, User.name, User.roll_no, User.oulad_student_id,
                  marks.c.average_marks, marks.c.assessment_count,
                  func.coalesce(engagement.c.clicks, 0).label("clicks"),
                  func.coalesce(engagement.c.active_days, 0).label("active_days"),
                  attendance.c.sessions, attendance.c.present)
         .filter(User.role == "student", User.active.is_(True))
         .outerjoin(marks, marks.c.student_id == User.id)
         .outerjoin(engagement, engagement.c.student_id == User.id)
         .outerjoin(attendance, attendance.c.student_id == User.id))
    # One compact aggregate row per student; no per-student query loop.
    rows = q.all()
    total_students = len(rows)
    at_risk = needs_attention = on_track = 0
    attention_rows = []
    score_values = []
    attendance_values = []
    for row in rows:
        avg = float(row.average_marks) if row.average_marks is not None else None
        att = round((int(row.present or 0) / int(row.sessions)) * 100, 1) if row.sessions else None
        if att is not None: attendance_values.append(att)
        label = risk_label(avg, int(row.clicks or 0), att)
        if label == "At Risk": at_risk += 1
        elif label == "Needs Attention": needs_attention += 1
        else: on_track += 1
        if avg is not None: score_values.append(avg)
        if label != "On Track":
            attention_rows.append({"id": row.id, "name": row.name, "roll_no": row.roll_no,
                "oulad_student_id": row.oulad_student_id, "average_marks": avg,
                "attendance": att, "engagement_clicks": int(row.clicks or 0),
                "active_days": int(row.active_days or 0), "status": label})
    attention_rows.sort(key=lambda x: (0 if x["status"] == "At Risk" else 1,
                                       x["average_marks"] if x["average_marks"] is not None else 101))
    subject_rows = (db.query(Subject.code, Subject.name, func.avg(AssessmentResult.score),
                             func.count(AssessmentResult.id))
        .join(Assessment, Assessment.subject_id == Subject.id)
        .join(AssessmentResult, AssessmentResult.assessment_id == Assessment.id)
        .filter(AssessmentResult.score.isnot(None))
        .group_by(Subject.code, Subject.name).order_by(Subject.code).all())
    subject_performance = [{"code": code, "subject": name,
                            "average": round(float(avg), 1), "assessment_count": int(count)}
                           for code, name, avg, count in subject_rows]
    return {"students": total_students,
            "average_marks": round(sum(score_values) / len(score_values), 1) if score_values else None,
            "attendance": round(sum(attendance_values) / len(attendance_values), 1) if attendance_values else None,
            "at_risk": at_risk, "needs_attention": needs_attention, "on_track": on_track,
            "subject_performance": subject_performance,
            "students_list": attention_rows[:8]}

@app.get("/api/students")
def list_students(q: str = "", status: str = "All", page: int = Query(1, ge=1),
                  limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
                  user: User = Depends(require_roles("teacher", "admin"))):
    marks, engagement, attendance = student_aggregate_query(db)
    base = (db.query(User.id, User.name, User.roll_no, User.oulad_student_id,
                     marks.c.average_marks, func.coalesce(engagement.c.clicks, 0).label("clicks"),
                     func.coalesce(engagement.c.active_days, 0).label("active_days"),
                     attendance.c.sessions, attendance.c.present)
            .filter(User.role == "student", User.active.is_(True))
            .outerjoin(marks, marks.c.student_id == User.id)
            .outerjoin(engagement, engagement.c.student_id == User.id)
            .outerjoin(attendance, attendance.c.student_id == User.id))
    if q.strip():
        term = f"%{q.strip()}%"
        base = base.filter(or_(User.name.ilike(term), User.roll_no.ilike(term),
                               User.email.ilike(term)))
    rows = base.order_by(User.oulad_student_id).all()
    filtered = []
    for row in rows:
        avg = float(row.average_marks) if row.average_marks is not None else None
        att = round((int(row.present or 0) / int(row.sessions)) * 100, 1) if row.sessions else None
        label = risk_label(avg, int(row.clicks or 0), att)
        if status != "All" and status != label: continue
        filtered.append({"id": row.id, "name": row.name, "roll_no": row.roll_no,
                         "oulad_student_id": row.oulad_student_id, "average_marks": avg,
                         "attendance": att, "engagement_clicks": int(row.clicks or 0),
                         "active_days": int(row.active_days or 0), "status": label})
    total = len(filtered)
    start = (page - 1) * limit
    return {"items": filtered[start:start + limit], "total": total,
            "page": page, "limit": limit, "pages": ceil(total / limit) if total else 0}

@app.get("/api/students/{student_id}")
def student_detail(student_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == "student" and user.id != student_id:
        raise HTTPException(status_code=403, detail="You can only view your own profile")
    student = db.get(User, student_id)
    if not student or student.role != "student":
        raise HTTPException(status_code=404, detail="Student not found")
    return student_detail_data(db, student)

@app.get("/api/subjects")
def subjects(db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = db.query(Subject).options(joinedload(Subject.teacher))
    if user.role == "student":
        query = query.join(Registration, Registration.subject_id == Subject.id).filter(Registration.student_id == user.id)
    return [{"id": s.id, "code": s.code, "name": s.name, "teacher": s.teacher.name,
             "semester": s.semester, "code_module": s.code_module,
             "code_presentation": s.code_presentation}
            for s in query.order_by(Subject.code).all()]

@app.get("/api/classes")
def classes(db: Session = Depends(get_db), user: User = Depends(current_user)):
    # ClassSession intentionally stores subject_id without an ORM relationship.
    # Join Subject explicitly instead of joinedload(ClassSession.subject).
    query = db.query(ClassSession, Subject).join(Subject, Subject.id == ClassSession.subject_id)
    if user.role == "student":
        query = query.join(
            Registration,
            Registration.subject_id == ClassSession.subject_id
        ).filter(Registration.student_id == user.id)
    rows = query.order_by(ClassSession.day, ClassSession.start_time).all()
    return [{"subject": subject.name, "code": subject.code, "day": session.day,
             "start": session.start_time, "end": session.end_time, "room": session.room}
            for session, subject in rows]

@app.post("/api/attendance")
def add_attendance(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    try:
        student_id = int(payload["student_id"]); subject_id = int(payload["subject_id"])
        class_date = date.fromisoformat(payload.get("class_date", date.today().isoformat()))
        present_value = payload["present"]
        present = present_value if isinstance(present_value, bool) else str(present_value).lower() == "true"
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Provide valid attendance details")
    if not db.get(User, student_id) or not db.get(Subject, subject_id):
        raise HTTPException(status_code=404, detail="Student or subject not found")
    existing = db.query(Attendance).filter_by(student_id=student_id, subject_id=subject_id, class_date=class_date).first()
    if existing:
        existing.present = present
        db.commit()
        return {"message": "Attendance updated", "id": existing.id}
    row = Attendance(student_id=student_id, subject_id=subject_id, class_date=class_date, present=present)
    db.add(row); db.commit()
    return {"message": "Attendance saved", "id": row.id}

@app.post("/api/marks")
def add_mark(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    try:
        student_id = int(payload["student_id"]); subject_id = int(payload["subject_id"])
        score = float(payload["score"]); max_score = float(payload.get("max_score", 100))
        assessment_name = str(payload.get("assessment", "Teacher-entered assessment"))[:40]
        if max_score <= 0 or score < 0 or score > max_score: raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Provide valid student, subject, score and maximum score")
    if not db.get(User, student_id) or not db.get(Subject, subject_id):
        raise HTTPException(status_code=404, detail="Student or subject not found")
    next_id = (db.query(func.min(Assessment.oulad_assessment_id)).scalar() or 0) - 1
    assessment = Assessment(subject_id=subject_id, oulad_assessment_id=next_id,
                            assessment_type=assessment_name, date=None, weight=0)
    db.add(assessment); db.flush()
    db.add(AssessmentResult(student_id=student_id, assessment_id=assessment.id, score=score / max_score * 100))
    db.commit()
    return {"message": "Supplemental assessment saved", "id": assessment.id}

@app.get("/api/assignments")
def assignments(user: User = Depends(current_user)):
    # OULAD has historical assessment deadlines, not current assignment content.
    return []

@app.get("/api/analytics/engagement")
def engagement_analytics(db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    rows = (db.query(Subject.code, Subject.name, func.sum(Engagement.total_clicks), func.avg(Engagement.total_clicks))
            .join(Engagement, Engagement.subject_id == Subject.id)
            .group_by(Subject.code, Subject.name).order_by(Subject.code).all())
    return [{"code": code, "subject": name, "total_clicks": int(total or 0),
             "average_clicks": round(float(avg or 0), 1)} for code, name, total, avg in rows]

@app.get("/api/analytics/performance")
def performance_analytics(db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    rows = (db.query(Subject.code, Subject.name, func.avg(AssessmentResult.score), func.count(AssessmentResult.id))
            .join(Assessment, Assessment.subject_id == Subject.id)
            .join(AssessmentResult, AssessmentResult.assessment_id == Assessment.id)
            .filter(AssessmentResult.score.isnot(None))
            .group_by(Subject.code, Subject.name).order_by(Subject.code).all())
    return [{"code": code, "subject": name, "average_score": round(float(avg or 0), 1),
             "assessment_count": int(count)} for code, name, avg, count in rows]
