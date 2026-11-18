"""Import the official OULAD CSV files into PostgreSQL.

The 10.6M-row studentVle.csv is streamed line-by-line. It is never loaded
into memory as a dataframe. Run once after starting the database:
    docker compose run --rm importer
"""
import csv
from collections import defaultdict
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from .models import User, Subject, Registration, Assessment, AssessmentResult, Engagement
from .auth import hash_password
from .seed import seed_staff

DATA = Path("data/oulad")
REQUIRED = ["studentInfo.csv", "studentAssessment.csv", "assessments.csv",
            "courses.csv", "studentRegistration.csv", "studentVle.csv", "vle.csv"]

def rows(filename):
    path = DATA / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Copy the seven official OULAD CSV files into data/oulad/")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)

def chunks(iterable, size=2000):
    batch=[]
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch=[]
    if batch:
        yield batch

def as_int(value):
    try: return int(value) if value not in ("", None) else None
    except (ValueError, TypeError): return None

def as_float(value):
    try: return float(value) if value not in ("", None) else None
    except (ValueError, TypeError): return None

def import_all():
    missing=[f for f in REQUIRED if not (DATA/f).exists()]
    if missing:
        raise FileNotFoundError("Missing OULAD files: " + ", ".join(missing))
    Base.metadata.create_all(engine)
    db: Session=SessionLocal()
    try:
        seed_staff(db)
        if db.query(Registration).count() > 0:
            print("OULAD import already exists. No duplicate import performed.")
            return
        teacher=db.query(User).filter(User.role=="teacher").first()
        print("1/7 Importing course presentations...")
        subject_map={}
        for r in rows("courses.csv"):
            key=(r["code_module"], r["code_presentation"])
            obj=Subject(code=f"{key[0]}-{key[1]}", code_module=key[0],
                        code_presentation=key[1], name=f"Module {key[0]} · Presentation {key[1]}",
                        teacher_id=teacher.id, semester=1)
            db.add(obj); db.flush()
            subject_map[key]=obj.id
        db.commit()

        print("2/7 Importing student identities...")
        student_map={}
        # studentInfo has one row per student-course registration, so the same
        # student ID can occur more than once. Create one login per unique ID.
        unique_student_ids=set()
        for r in rows("studentInfo.csv"):
            unique_student_ids.add(int(r["id_student"]))
        demo_student_hash=hash_password("Student@123")
        for batch in chunks(sorted(unique_student_ids), 1500):
            for sid in batch:
                user=User(name=f"OULAD Student {sid}", email=f"student{sid}@oulad.local",
                          password_hash=demo_student_hash, role="student",
                          department="Open University Learning Analytics", roll_no=str(sid),
                          semester=1, oulad_student_id=sid)
                db.add(user); db.flush()
                student_map[sid]=user.id
            db.commit()
        print(f"   Created {len(student_map):,} unique student accounts.")

        print("3/7 Importing student-course registrations...")
        registration_count=0
        for batch in chunks(rows("studentInfo.csv"), 1500):
            for r in batch:
                sid=int(r["id_student"]); key=(r["code_module"],r["code_presentation"])
                db.add(Registration(student_id=student_map[sid], subject_id=subject_map[key],
                    gender=r.get("gender"), region=r.get("region"),
                    highest_education=r.get("highest_education"), imd_band=r.get("imd_band"),
                    age_band=r.get("age_band"), num_of_prev_attempts=as_int(r.get("num_of_prev_attempts")),
                    studied_credits=as_int(r.get("studied_credits")), disability=r.get("disability"),
                    final_result=r.get("final_result")))
                registration_count+=1
            db.commit()
        print(f"   Imported {registration_count:,} registrations.")

        print("4/7 Importing assessment definitions...")
        assessment_map={}
        for r in rows("assessments.csv"):
            key=(r["code_module"],r["code_presentation"],int(r["id_assessment"]))
            subject_id=subject_map[(r["code_module"],r["code_presentation"])]
            obj=Assessment(subject_id=subject_id,oulad_assessment_id=key[2],
                assessment_type=r.get("assessment_type"),date=as_int(r.get("date")),
                weight=as_float(r.get("weight")) or 0)
            db.add(obj); db.flush(); assessment_map[key[2]]=obj.id
        db.commit()

        print("5/7 Importing assessment scores...")
        result_count=0
        for batch in chunks(rows("studentAssessment.csv"), 3000):
            for r in batch:
                student_id=student_map.get(as_int(r.get("id_student")))
                assessment_id=assessment_map.get(as_int(r.get("id_assessment")))
                if student_id and assessment_id:
                    db.add(AssessmentResult(student_id=student_id,assessment_id=assessment_id,
                                            score=as_float(r.get("score"))))
                    result_count+=1
            db.commit()
        print(f"   Imported {result_count:,} assessment results.")

        print("6/7 Aggregating the 10.6M VLE interaction rows (streaming)...")
        # Aggregate per student + module + presentation; only a small dictionary is retained.
        clicks=defaultdict(int); active_days=defaultdict(set)
        for idx,r in enumerate(rows("studentVle.csv"), start=1):
            key=(as_int(r.get("id_student")),r.get("code_module"),r.get("code_presentation"))
            if key[0] is not None:
                clicks[key]+=as_int(r.get("sum_click")) or 0
                activity_day=as_int(r.get("date"))
                if activity_day is not None:
                    active_days[key].add(activity_day)
            if idx % 1_000_000 == 0:
                print(f"   Processed {idx:,} VLE rows...")
        engagement_count=0
        for key,total in clicks.items():
            sid,module,presentation=key
            student_id=student_map.get(sid); subject_id=subject_map.get((module,presentation))
            if student_id and subject_id:
                db.add(Engagement(student_id=student_id,subject_id=subject_id,
                                  total_clicks=total,active_days=len(active_days[key])))
                engagement_count+=1
            if engagement_count % 3000 == 0:
                db.commit()
        db.commit()
        print(f"   Saved {engagement_count:,} student-course engagement summaries.")

        print("7/7 Import complete.")
        print(f"Students: {len(student_map):,} | Registrations: {registration_count:,} | "
              f"Assessment results: {result_count:,} | Engagement summaries: {engagement_count:,}")
    finally:
        db.close()

if __name__ == "__main__":
    import_all()
