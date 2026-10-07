from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date
from pathlib import Path

import models
from database import engine, get_db


# =========================================================
# DATABASE
# =========================================================

# Create database tables automatically
models.Base.metadata.create_all(bind=engine)


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(title="Student Attendance Portal")


# =========================================================
# JINJA2 TEMPLATES
# =========================================================

# Project structure:
#
# portal/
# ├── backend/
# │   └── main.py
# ├── frontend/
# │   └── index.html
# ├── database.py
# └── models.py

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

templates = Jinja2Templates(directory=str(FRONTEND_DIR))


# =========================================================
# STARTUP - ADD SAMPLE STUDENTS
# =========================================================

@app.on_event("startup")
def startup_populate_db():

    db = next(get_db())

    try:
        # Add sample students only if database is empty
        if db.query(models.Student).count() == 0:

            sample_students = [
                models.Student(
                    roll_no="101",
                    name="Aarav Sharma",
                    student_class="Class 10A"
                ),

                models.Student(
                    roll_no="102",
                    name="Diya Patel",
                    student_class="Class 10A"
                ),

                models.Student(
                    roll_no="103",
                    name="Rohan Verma",
                    student_class="Class 10A"
                ),

                models.Student(
                    roll_no="104",
                    name="Ananya Reddy",
                    student_class="Class 10A"
                )
            ]

            db.add_all(sample_students)
            db.commit()

    finally:
        db.close()


# =========================================================
# ROUTE 1 - MAIN ATTENDANCE DASHBOARD
# =========================================================

@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    selected_date: str = None,
    db: Session = Depends(get_db)
):

    # -----------------------------------------------------
    # Get selected date
    # -----------------------------------------------------

    if selected_date:

        try:
            target_date = datetime.strptime(
                selected_date,
                "%Y-%m-%d"
            ).date()

        except ValueError:
            target_date = date.today()

    else:
        target_date = date.today()


    # Convert date to string for HTML
    selected_date_str = target_date.strftime("%Y-%m-%d")


    # -----------------------------------------------------
    # Get all students
    # -----------------------------------------------------

    students = (
        db.query(models.Student)
        .order_by(models.Student.roll_no)
        .all()
    )


    # -----------------------------------------------------
    # Get attendance for selected date
    # -----------------------------------------------------

    attendance_map = {}

    records = (
        db.query(models.Attendance)
        .filter(
            models.Attendance.date == target_date
        )
        .all()
    )

    for record in records:

        attendance_map[record.student_id] = record.status


    # -----------------------------------------------------
    # Prepare student data for HTML
    # -----------------------------------------------------

    student_list = []

    for student in students:

        student_list.append({

            "id": student.id,

            "roll_no": student.roll_no,

            "name": student.name,

            "student_class": student.student_class,

            # Default attendance is Present
            # if no attendance has been saved yet
            "status": attendance_map.get(
                student.id,
                "Present"
            )
        })


    # -----------------------------------------------------
    # Calculate attendance statistics
    # FOR THE SELECTED DATE
    # -----------------------------------------------------

    total_students = (
        db.query(models.Student).count()
    )


    present_count = (
        db.query(models.Attendance)
        .filter(
            models.Attendance.date == target_date,
            models.Attendance.status == "Present"
        )
        .count()
    )


    absent_count = (
        db.query(models.Attendance)
        .filter(
            models.Attendance.date == target_date,
            models.Attendance.status == "Absent"
        )
        .count()
    )


    late_count = (
        db.query(models.Attendance)
        .filter(
            models.Attendance.date == target_date,
            models.Attendance.status == "Late"
        )
        .count()
    )


    # -----------------------------------------------------
    # Statistics dictionary
    # -----------------------------------------------------

    stats = {

        "total_students": total_students,

        "present": present_count,

        "absent": absent_count,

        "late": late_count
    }


    # -----------------------------------------------------
    # SEND DATA TO index.html
    # -----------------------------------------------------

    return templates.TemplateResponse(

        request=request,

        name="index.html",

        context={

            "request": request,

            "students": student_list,

            "selected_date": selected_date_str,

            "stats": stats
        }
    )


# =========================================================
# ROUTE 2 - ADD NEW STUDENT
# =========================================================

@app.post("/add-student")
def add_student(

    roll_no: str = Form(...),

    name: str = Form(...),

    student_class: str = Form(...),

    db: Session = Depends(get_db)
):

    # -----------------------------------------------------
    # Check if roll number already exists
    # -----------------------------------------------------

    existing_student = (
        db.query(models.Student)
        .filter(
            models.Student.roll_no == roll_no
        )
        .first()
    )


    if existing_student:

        raise HTTPException(

            status_code=400,

            detail="Roll number already exists"
        )


    # -----------------------------------------------------
    # Create new student
    # -----------------------------------------------------

    new_student = models.Student(

        roll_no=roll_no,

        name=name,

        student_class=student_class
    )


    db.add(new_student)

    db.commit()


    # -----------------------------------------------------
    # Return to dashboard
    # -----------------------------------------------------

    return RedirectResponse(

        url="/",

        status_code=303
    )


# =========================================================
# ROUTE 3 - SAVE / UPDATE ATTENDANCE
# =========================================================

@app.post("/save-attendance")
async def save_attendance(

    request: Request,

    db: Session = Depends(get_db)
):

    # -----------------------------------------------------
    # Read submitted form
    # -----------------------------------------------------

    form_data = await request.form()


    # Get selected attendance date
    date_str = form_data.get("attendance_date")


    if not date_str:

        raise HTTPException(

            status_code=400,

            detail="Attendance date is required"
        )


    # -----------------------------------------------------
    # Convert date string to Python date
    # -----------------------------------------------------

    try:

        target_date = datetime.strptime(

            date_str,

            "%Y-%m-%d"

        ).date()

    except ValueError:

        raise HTTPException(

            status_code=400,

            detail="Invalid date format"
        )


    # -----------------------------------------------------
    # Process attendance
    # -----------------------------------------------------

    for key, value in form_data.items():

        # Example:
        # status_1 = Present
        # status_2 = Absent

        if key.startswith("status_"):

            try:

                student_id = int(
                    key.split("_")[1]
                )

            except (ValueError, IndexError):

                continue


            status = str(value)


            # -------------------------------------------------
            # Validate attendance status
            # -------------------------------------------------

            if status not in [
                "Present",
                "Absent",
                "Late"
            ]:

                continue


            # -------------------------------------------------
            # Check existing attendance record
            # -------------------------------------------------

            record = (
                db.query(models.Attendance)
                .filter(

                    models.Attendance.student_id
                    == student_id,

                    models.Attendance.date
                    == target_date

                )
                .first()
            )


            # -------------------------------------------------
            # Update existing record
            # -------------------------------------------------

            if record:

                record.status = status


            # -------------------------------------------------
            # Create new record
            # -------------------------------------------------

            else:

                new_record = models.Attendance(

                    student_id=student_id,

                    date=target_date,

                    status=status
                )

                db.add(new_record)


    # -----------------------------------------------------
    # Save changes
    # -----------------------------------------------------

    db.commit()


    # -----------------------------------------------------
    # Return to selected date
    # -----------------------------------------------------

    return RedirectResponse(

        url=f"/?selected_date={date_str}",

        status_code=303
    )