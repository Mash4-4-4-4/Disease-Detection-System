import os
from functools import wraps
import random  # ✅ for random doctor selection

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from pymongo import MongoClient
import pickle
import numpy as np
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import certifi


# ---------- Config ----------
load_dotenv("main.env")


SECRET_KEY = os.getenv("SECRET_KEY", "change_this_dev_secret")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ---------- Database ----------
from pymongo import MongoClient
import certifi

MONGO_URI = "mongodb+srv://dds_user:8pf8ict98YRNu3A4@cluster0.lcf2ezo.mongodb.net/DDS?retryWrites=true&w=majority"

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())

db = client["DDS"]   # ✅ IMPORTANT CHANGE
users = db["users"]
users = db["users"]
predictions = db["predictions"]

# ---------- Fake Doctors (static dataset) ----------
appt_doctors = [
    {
        "name": "Dr. Aarav Mehta", "speciality": "Endocrinologist",
        "experience": 9, "fee": 600, "distance_km": 3.2,
        "address": "Lotus Clinic, Andheri East",
        "slots": ["Today 6:00 PM", "Today 7:30 PM", "Tomorrow 10:15 AM"]
    },
    {
        "name": "Dr. Priya Sharma", "speciality": "Diabetologist",
        "experience": 6, "fee": 500, "distance_km": 2.1,
        "address": "Green Leaf Hospital, Powai",
        "slots": ["Today 4:30 PM", "Tomorrow 9:30 AM", "Tomorrow 1:00 PM"]
    },
    {
        "name": "Dr. Rohan Verma", "speciality": "Internal Medicine",
        "experience": 11, "fee": 750, "distance_km": 5.4,
        "address": "CityCare Centre, Bandra West",
        "slots": ["Today 7:15 PM", "Tomorrow 11:45 AM", "Tomorrow 4:00 PM"]
    },
    {
        "name": "Dr. Kavya Das", "speciality": "General Physician",
        "experience": 4, "fee": 450, "distance_km": 1.9,
        "address": "Sunrise Polyclinic, Juhu",
        "slots": ["Today 5:20 PM", "Today 6:40 PM", "Tomorrow 12:30 PM"]
    },
    {
        "name": "Dr. Ishaan Patel", "speciality": "Endocrinologist",
        "experience": 10, "fee": 700, "distance_km": 4.7,
        "address": "Wellness Point, Vile Parle",
        "slots": ["Today 8:00 PM", "Tomorrow 10:30 AM", "Tomorrow 3:30 PM"]
    },
    {
        "name": "Dr. Neha Kapoor", "speciality": "Diabetologist",
        "experience": 7, "fee": 550, "distance_km": 3.8,
        "address": "HealthFirst Clinic, Santacruz East",
        "slots": ["Today 3:45 PM", "Today 6:10 PM", "Tomorrow 2:15 PM"]
    },
]

def pick_random_doctors(min_n=3, max_n=6):
    """Pick N random doctors and attach a chosen next slot."""
    n = random.randint(min_n, max_n)
    n = min(n, len(appt_doctors))
    chosen = random.sample(appt_doctors, n)
    enriched = []
    for d in chosen:
        slot = random.choice(d["slots"]) if d.get("slots") else "Today 5:00 PM"
        enriched.append({**d, "next_slot": slot})
    return enriched


# ---------- ML Model (existing) ----------
try:
    with open("diabetesmodel.pkl", "rb") as model_file:
        model = pickle.load(model_file)
    with open("scaler.pkl", "rb") as scaler_file:
        scaler = pickle.load(scaler_file)
except Exception:
    model = None
    scaler = None


# ---------- Helpers ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_email" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return wrapper

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


# ---------- Routes ----------
@app.route("/")
def home_page():
    return render_template("home.html")

@app.route("/login", methods=["GET"])
def login_page():
    return render_template("index.html")

@app.route("/login", methods=["POST"])
def login():
    email = normalize_email(request.form.get("email"))
    password = request.form.get("password", "")

    if not email or not password:
        flash("Email and password are required.", "error")
        return redirect(url_for("login_page"))

    user = users.find_one({"email": email})
    if not user:
        flash("User not found. Please register an account.", "warning")
        return redirect(url_for("login_page"))

    if not user.get("password_hash"):
        flash("This account doesn't have a password set. Please register again.", "error")
        return redirect(url_for("register_page"))

    if not check_password_hash(user["password_hash"], password):
        flash("Incorrect password. Please try again.", "error")
        return redirect(url_for("login_page"))

    session["user_email"] = email
    session["user_name"] = user.get("name")
    flash("Logged in successfully.", "success")
    return redirect(url_for("home_page"))

@app.route("/register", methods=["GET"])
def register_page():
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def register():
    email = normalize_email(request.form.get("email"))
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not email or not password or not confirm_password:
        flash("All fields are required.", "error")
        return redirect(url_for("register_page"))

    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("register_page"))

    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("register_page"))

    existing = users.find_one({"email": email})
    if existing:
        flash("Account already exists. Please log in.", "warning")
        return redirect(url_for("login_page"))

    session["pending_email"] = email
    session["pending_password_hash"] = generate_password_hash(password)
    flash("Account created. Please complete your basic info.", "info")
    return redirect(url_for("info_page"))

@app.route("/info", methods=["GET"])
def info_page():
    pending_email = session.get("pending_email")
    if not pending_email:
        flash("Please register first.", "warning")
        return redirect(url_for("register_page"))
    return render_template("info.html", pending_email=pending_email)

@app.route("/save_info", methods=["POST"])
def save_info():
    pending_email = normalize_email(session.get("pending_email"))
    pending_password_hash = session.get("pending_password_hash")

    if not pending_email or not pending_password_hash:
        flash("Session expired. Please register again.", "error")
        return redirect(url_for("register_page"))

    # profile fields
    name = request.form.get("name")
    age = request.form.get("age")
    gender = request.form.get("gender")
    country = request.form.get("country")
    height = request.form.get("height")
    weight = request.form.get("weight")
    blood_group = request.form.get("blood_group")
    smoking = request.form.get("smoking")
    drinking = request.form.get("drinking")
    exercise = request.form.get("exercise")
    diet = request.form.get("diet")
    phone = request.form.get("phone")

    users.update_one(
        {"email": pending_email},
        {
            "$set": {
                "email": pending_email,
                "password_hash": pending_password_hash,
                "name": name,
                "age": age,
                "gender": gender,
                "country": country,
                "height": height,
                "weight": weight,
                "blood_group": blood_group,
                "habits": {
                    "smoking": smoking, "drinking": drinking,
                    "exercise": exercise, "diet": diet
                },
                "phone": phone,
            }
        },
        upsert=True,
    )

    session.pop("pending_password_hash", None)
    session.pop("pending_email", None)
    session["user_email"] = pending_email
    session["user_name"] = name

    flash("Profile saved. Welcome!", "success")
    return redirect(url_for("home_page"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("home_page"))

@app.route("/predict", methods=["GET"])
@login_required
def predict_page():
    prediction = session.pop("latest_prediction", None)
    probability = session.pop("latest_probability", None)

    # ✅ always send a fresh list of random doctors for sidebar
    appt_doctors = pick_random_doctors()

    return render_template(
        "form.html",
        prediction=prediction,
        probability=probability,
        appt_doctors=appt_doctors
    )





@app.route("/form", methods=["POST"])
@login_required
def predict_form():
   

    if model is None or scaler is None:
        return "Model files not found. Please add diabetesmodel.pkl and scaler.pkl to the project root."

    try:
        pregnancies = float(request.form['preg'])
        glucose = float(request.form['glu'])
        bloodpressure = float(request.form['bp'])
        skinthickness = float(request.form['skin'])
        insulin = float(request.form['insulin'])
        bmi = float(request.form['BMI'])
        dpf = float(request.form['pedigree'])
        age = float(request.form['age'])

        input_data = np.array([
            pregnancies, glucose, bloodpressure, skinthickness,
            insulin, bmi, dpf, age
        ]).reshape(1, -1)

        scaled_data = scaler.transform(input_data)
        prediction = model.predict(scaled_data)
        result = "Diabetic" if prediction[0] == 1 else "Not Diabetic"

        # Probability (if available)
        prob = None
        try:
            proba = model.predict_proba(scaled_data)[0][1]
            prob = float(proba)
        except Exception:
            pass

        # Save result in DB
        predictions.insert_one({
            "email": session.get("user_email"),
            "result": result,
            "probability": prob,
            "inputs": {
                "pregnancies": pregnancies,
                "glucose": glucose,
                "bloodpressure": bloodpressure,
                "skinthickness": skinthickness,
                "insulin": insulin,
                "bmi": bmi,
                "dpf": dpf,
                "age": age,
            },
            "created_at": datetime.utcnow()
        })



        # Store for GET /predict (show once)
        session["latest_prediction"] = result
        session["latest_probability"] = None if prob is None else round(prob, 4)
    

        return redirect(url_for("predict_page"))

    except Exception as e:
        return f"Error: {str(e)}"


# ---------- PDF Report ----------
def _draw_key_value(c, y, key, value, key_w=60*mm, page_w=210*mm, margin=15*mm):
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, f"{key}:")
    c.setFont("Helvetica", 10)
    c.drawString(margin + key_w, y, f"{value}")
    return y - 8*mm

@app.route("/download_report")
@login_required
def download_report():
    email = session.get("user_email")
    user = users.find_one({"email": email}) or {}
    latest = predictions.find_one({"email": email}, sort=[("created_at", -1)])

    if latest is None:
        flash("No prediction found. Please run a prediction first.", "warning")
        return redirect(url_for("predict_page"))

    # Collect fields safely
    name = user.get("name", "-")
    age = user.get("age", "-")
    gender = user.get("gender", "-")
    height = user.get("height", "-")
    weight = user.get("weight", "-")
    blood_group = user.get("blood_group", "-")

    habits = user.get("habits", {}) or {}
    smoking = habits.get("smoking", "-")
    drinking = habits.get("drinking", "-")
    exercise = habits.get("exercise", "-")
    diet = habits.get("diet", "-")

    result = latest.get("result", "-")
    probability = latest.get("probability", None)
    created_at = latest.get("created_at", datetime.utcnow())

    # Build PDF in memory
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 15*mm
    y = height - margin

    # Header
    c.setFillColor(colors.HexColor("#0077FF"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "MediScanAI – Diagnostic Report")
    y -= 10*mm

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, f"Email: {email}")
    c.drawRightString(width - margin, y, created_at.strftime("Generated on: %Y-%m-%d %H:%M UTC"))
    y -= 8*mm

    # Divider
    c.setStrokeColor(colors.HexColor("#0077FF"))
    c.setLineWidth(1)
    c.line(margin, y, width - margin, y)
    y -= 10*mm

    # Patient details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Patient Profile")
    y -= 9*mm

    y = _draw_key_value(c, y, "Name", name)
    y = _draw_key_value(c, y, "Age", age)
    y = _draw_key_value(c, y, "Gender", gender)
    y = _draw_key_value(c, y, "Height (cm)", height)
    y = _draw_key_value(c, y, "Weight (kg)", weight)
    y = _draw_key_value(c, y, "Blood Group", blood_group)
    y -= 4*mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Lifestyle")
    y -= 9*mm

    y = _draw_key_value(c, y, "Smoking", smoking)
    y = _draw_key_value(c, y, "Drinking", drinking)
    y = _draw_key_value(c, y, "Exercise", exercise)
    y = _draw_key_value(c, y, "Diet", diet)
    y -= 6*mm

    # Divider
    c.setStrokeColor(colors.HexColor("#00B3C7"))
    c.setLineWidth(0.7)
    c.line(margin, y, width - margin, y)
    y -= 10*mm

    # Prediction
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Prediction Result")
    y -= 9*mm

    # Result badge
    if result == "Diabetic":
        c.setFillColor(colors.HexColor("#ff6b6b"))
        label = "DIABETIC ⚠"
    else:
        c.setFillColor(colors.HexColor("#3ddc84"))
        label = "NOT DIABETIC ✅"

    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, label)
    c.setFillColor(colors.black)
    y -= 10*mm

    # Optional probability
    if probability is not None:
        c.setFont("Helvetica", 10)
        c.drawString(margin, y, f"Model probability (positive class): {probability:.2%}")
        y -= 8*mm

    # Footer note
    y -= 6*mm
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.grey)
    c.drawString(margin, y, "Note: This report is AI-generated and intended for informational purposes only. Please consult a medical professional for diagnosis.")
    c.setFillColor(colors.black)

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"MediScanAI_Report_{(name or 'User').replace(' ', '_')}_{created_at.strftime('%Y-%m-%d')}.pdf"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
