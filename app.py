# dental_clinic_app.py
# متكامل: إدارة عيادة، مالية، إدخال يومي، تقارير، واجهة محسّنة
# تشغيل: streamlit run dental_clinic_app.py

import streamlit as st
import pandas as pd
import datetime
import os
import io
import uuid
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import plotly.express as px

# Optional visual menu (install streamlit-option-menu in requirements if available)
try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except Exception:
    HAS_OPTION_MENU = False

# ---------------------------
# Config
# ---------------------------
DB_URI = "sqlite:///dental_clinic.db"
IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)

# ---------------------------
# Database setup
# ---------------------------
engine = create_engine(DB_URI, echo=False, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()

# ---------------------------
# Models
# ---------------------------
class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    gender = Column(String)
    phone = Column(String)
    address = Column(String)
    medical_history = Column(Text)
    image_path = Column(String)

class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    specialty = Column(String)
    phone = Column(String)
    email = Column(String)

class Treatment(Base):
    __tablename__ = "treatments"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    base_cost = Column(Float, default=0.0)

class TreatmentPercentage(Base):
    __tablename__ = "treatment_percentages"
    id = Column(Integer, primary_key=True)
    treatment_id = Column(Integer, ForeignKey("treatments.id"))
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    clinic_percentage = Column(Float)
    doctor_percentage = Column(Float)
    treatment = relationship("Treatment")
    doctor = relationship("Doctor")

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    treatment_id = Column(Integer, ForeignKey("treatments.id"))
    date = Column(DateTime)
    status = Column(String)
    notes = Column(Text)
    patient = relationship("Patient")
    doctor = relationship("Doctor")
    treatment = relationship("Treatment")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    total_amount = Column(Float)
    paid_amount = Column(Float)
    clinic_share = Column(Float)
    doctor_share = Column(Float)
    payment_method = Column(String)
    discounts = Column(Float)
    taxes = Column(Float)
    date_paid = Column(DateTime)
    appointment = relationship("Appointment")

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    description = Column(String)
    category = Column(String)
    amount = Column(Float)
    date = Column(DateTime)

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    quantity = Column(Float, default=0.0)
    unit = Column(String)
    cost_per_unit = Column(Float, default=0.0)
    low_threshold = Column(Float, default=5.0)

class DailyTransaction(Base):
    __tablename__ = "daily_transactions"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.datetime.now)
    income = Column(Float, default=0.0)
    expense = Column(Float, default=0.0)
    notes = Column(Text)

Base.metadata.create_all(engine)

# ---------------------------
# Session context manager
# ---------------------------
@contextmanager
def session_scope():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# ---------------------------
# Utilities
# ---------------------------
def secure_filename(filename):
    base, ext = os.path.splitext(filename) if filename else ("file", ".png")
    return f"{uuid.uuid4().hex}{ext}"

def save_uploaded_image(uploaded_file, prefix="img"):
    if uploaded_file is None:
        return None
    filename = secure_filename(getattr(uploaded_file, "name", None))
    path = os.path.join(IMAGES_DIR, f"{prefix}_{filename}")
    with open(path, "wb") as f:
        f.write(uploaded_file.getvalue())
    return path

def datetime_input(label, default=None):
    if default is None:
        default = datetime.datetime.now()
    date = st.date_input(f"{label} - التاريخ", value=default.date())
    time = st.time_input(f"{label} - الوقت", value=default.time())
    return datetime.datetime.combine(date, time)

def df_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
        writer.save()
    output.seek(0)
    return output.getvalue()

def generate_invoice_pdf_buffer(payment_id=None, appointment_id=None):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "فاتورة - عيادة الأسنان")
    y -= 30
    with session_scope() as s:
        if payment_id:
            p = s.get(Payment, payment_id)
            if p:
                appt = p.appointment
                c.setFont("Helvetica", 11)
                c.drawString(50, y, f"تاريخ الدفع: {p.date_paid.strftime('%Y-%m-%d %H:%M') if p.date_paid else ''}")
                y -= 20
                if appt:
                    c.drawString(50, y, f"المريض: {appt.patient.name if appt.patient else ''}")
                    y -= 15
                    c.drawString(50, y, f"الطبيب: {appt.doctor.name if appt.doctor else ''}")
                    y -= 15
                    c.drawString(50, y, f"العلاج: {appt.treatment.name if appt.treatment else ''}")
                    y -= 20
                c.drawString(50, y, f"المبلغ الإجمالي: {p.total_amount}")
                y -= 15
                c.drawString(50, y, f"الخصم: {p.discounts or 0.0}")
                y -= 15
                c.drawString(50, y, f"الضريبة: {p.taxes or 0.0}")
                y -= 15
                c.drawString(50, y, f"حصة العيادة: {p.clinic_share}")
                y -= 15
                c.drawString(50, y, f"حصة الطبيب: {p.doctor_share}")
                y -= 15
                c.drawString(50, y, f"المدفوع: {p.paid_amount}")
                y -= 30
        elif appointment_id:
            a = s.get(Appointment, appointment_id)
            if a:
                c.setFont("Helvetica", 11)
                c.drawString(50, y, f"تاريخ الموعد: {a.date.strftime('%Y-%m-%d %H:%M') if a.date else ''}")
                y -= 20
                c.drawString(50, y, f"المريض: {a.patient.name if a.patient else ''}")
                y -= 15
                c.drawString(50, y, f"الطبيب: {a.doctor.name if a.doctor else ''}")
                y -= 15
                c.drawString(50, y, f"العلاج: {a.treatment.name if a.treatment else ''}")
                y -= 15
                c.drawString(50, y, f"ملاحظات: {a.notes or ''}")
                y -= 20
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ---------------------------
# Core CRUD + safe GETs (return dicts)
# ---------------------------

# Patients
def add_patient(name, age=None, gender=None, phone=None, address=None, medical_history=None, image=None):
    with session_scope() as s:
        p = Patient(name=name, age=age, gender=gender, phone=phone, address=address, medical_history=medical_history)
        if image:
            p.image_path = save_uploaded_image(image, prefix="patient")
        s.add(p)
        s.flush()
        return p.id

def edit_patient(patient_id, name, age, gender, phone, address, medical_history, image=None):
    with session_scope() as s:
        p = s.get(Patient, patient_id)
        if not p:
            return False
        p.name = name
        p.age = age
        p.gender = gender
        p.phone = phone
        p.address = address
        p.medical_history = medical_history
        if image:
            p.image_path = save_uploaded_image(image, prefix="patient")
        return True

def delete_patient(patient_id):
    with session_scope() as s:
        p = s.get(Patient, patient_id)
        if not p:
            return False
        s.delete(p)
        return True

def get_patients():
    with session_scope() as s:
        rows = s.query(Patient).order_by(Patient.id).all()
        data = []
        for r in rows:
            data.append({
                "id": r.id,
                "name": r.name,
                "age": r.age,
                "gender": r.gender,
                "phone": r.phone,
                "address": r.address,
                "medical_history": r.medical_history,
                "image_path": r.image_path
            })
        return data

# Doctors
def add_doctor(name, specialty=None, phone=None, email=None):
    with session_scope() as s:
        d = Doctor(name=name, specialty=specialty, phone=phone, email=email)
        s.add(d); s.flush(); return d.id

def edit_doctor(doctor_id, name, specialty, phone, email):
    with session_scope() as s:
        d = s.get(Doctor, doctor_id)
        if not d: return False
        d.name = name; d.specialty = specialty; d.phone = phone; d.email = email
        return True

def delete_doctor(doctor_id):
    with session_scope() as s:
        d = s.get(Doctor, doctor_id)
        if not d: return False
        s.delete(d); return True

def get_doctors():
    with session_scope() as s:
        rows = s.query(Doctor).order_by(Doctor.id).all()
        return [{"id": r.id, "name": r.name, "specialty": r.specialty, "phone": r.phone, "email": r.email} for r in rows]

# Treatments
def add_treatment(name, base_cost=0.0):
    with session_scope() as s:
        t = Treatment(name=name, base_cost=base_cost); s.add(t); s.flush(); return t.id

def edit_treatment(treatment_id, name, base_cost):
    with session_scope() as s:
        t = s.get(Treatment, treatment_id)
        if not t: return False
        t.name = name; t.base_cost = base_cost; return True

def delete_treatment(treatment_id):
    with session_scope() as s:
        t = s.get(Treatment, treatment_id)
        if not t: return False
        s.delete(t); return True

def get_treatments():
    with session_scope() as s:
        rows = s.query(Treatment).order_by(Treatment.id).all()
        return [{"id": r.id, "name": r.name, "base_cost": r.base_cost} for r in rows]

# Treatment percentages
def set_treatment_percentage(treatment_id, doctor_id, clinic_percentage, doctor_percentage):
    with session_scope() as s:
        tp = s.query(TreatmentPercentage).filter_by(treatment_id=treatment_id, doctor_id=doctor_id).first()
        if not tp:
            tp = TreatmentPercentage(treatment_id=treatment_id, doctor_id=doctor_id, clinic_percentage=clinic_percentage, doctor_percentage=doctor_percentage)
            s.add(tp)
        else:
            tp.clinic_percentage = clinic_percentage; tp.doctor_percentage = doctor_percentage
        s.flush(); return True

def get_treatment_percentages():
    with session_scope() as s:
        rows = s.query(TreatmentPercentage).order_by(TreatmentPercentage.id).all()
        data = []
        for r in rows:
            data.append({
                "id": r.id,
                "treatment_id": r.treatment_id,
                "treatment_name": r.treatment.name if r.treatment else None,
                "doctor_id": r.doctor_id,
                "doctor_name": r.doctor.name if r.doctor else None,
                "clinic_percentage": r.clinic_percentage,
                "doctor_percentage": r.doctor_percentage
            })
        return data

# Appointments
def add_appointment(patient_id, doctor_id, treatment_id, date, status="مجدول", notes=None):
    with session_scope() as s:
        a = Appointment(patient_id=patient_id, doctor_id=doctor_id, treatment_id=treatment_id, date=date, status=status, notes=notes)
        s.add(a); s.flush(); return a.id

def edit_appointment(appointment_id, patient_id, doctor_id, treatment_id, date, status, notes):
    with session_scope() as s:
        a = s.get(Appointment, appointment_id)
        if not a: return False
        a.patient_id = patient_id; a.doctor_id = doctor_id; a.treatment_id = treatment_id; a.date = date; a.status = status; a.notes = notes
        return True

def delete_appointment(appointment_id):
    with session_scope() as s:
        a = s.get(Appointment, appointment_id)
        if not a: return False
        s.delete(a); return True

def get_appointments():
    with session_scope() as s:
        rows = s.query(Appointment).order_by(Appointment.date.desc()).all()
        data = []
        for r in rows:
            data.append({
                "id": r.id,
                "patient_id": r.patient_id,
                "patient_name": r.patient.name if r.patient else None,
                "doctor_id": r.doctor_id,
                "doctor_name": r.doctor.name if r.doctor else None,
                "treatment_id": r.treatment_id,
                "treatment_name": r.treatment.name if r.treatment else None,
                "date": r.date,
                "status": r.status,
                "notes": r.notes
            })
        return data

# Payments
def calculate_shares(appointment_id, total_amount, discounts=0.0, taxes=0.0):
    with session_scope() as s:
        appointment = s.get(Appointment, appointment_id) if appointment_id else None
        if appointment:
            perc = s.query(TreatmentPercentage).filter_by(treatment_id=appointment.treatment_id, doctor_id=appointment.doctor_id).first()
            if perc:
                clinic_perc = perc.clinic_percentage or 50.0; doctor_perc = perc.doctor_percentage or 50.0
            else:
                clinic_perc = doctor_perc = 50.0
        else:
            clinic_perc = doctor_perc = 50.0
    net = float(total_amount) - float(discounts or 0.0) + float(taxes or 0.0)
    clinic = round(net * (clinic_perc / 100.0), 2)
    doctor = round(net * (doctor_perc / 100.0), 2)
    return clinic, doctor

def add_payment(appointment_id, total_amount, paid_amount, payment_method, discounts=0.0, taxes=0.0):
    clinic_share, doctor_share = calculate_shares(appointment_id, total_amount, discounts, taxes)
    with session_scope() as s:
        p = Payment(appointment_id=appointment_id, total_amount=total_amount, paid_amount=paid_amount,
                    clinic_share=clinic_share, doctor_share=doctor_share,
                    payment_method=payment_method, discounts=discounts, taxes=taxes, date_paid=datetime.datetime.now())
        s.add(p); s.flush(); return p.id

def delete_payment(payment_id):
    with session_scope() as s:
        p = s.get(Payment, payment_id)
        if not p: return False
        s.delete(p); return True

def get_payments():
    with session_scope() as s:
        rows = s.query(Payment).order_by(Payment.date_paid.desc()).all()
        data = []
        for r in rows:
            data.append({
                "id": r.id,
                "appointment_id": r.appointment_id,
                "total_amount": r.total_amount,
                "paid_amount": r.paid_amount,
                "clinic_share": r.clinic_share,
                "doctor_share": r.doctor_share,
                "payment_method": r.payment_method,
                "discounts": r.discounts,
                "taxes": r.taxes,
                "date_paid": r.date_paid
            })
        return data

# Expenses
def add_expense(description, amount, category=None, date=None):
    if date is None: date = datetime.datetime.now()
    with session_scope() as s:
        e = Expense(description=description, amount=amount, category=category, date=date)
        s.add(e); s.flush(); return e.id

def delete_expense(expense_id):
    with session_scope() as s:
        e = s.get(Expense, expense_id)
        if not e: return False
        s.delete(e); return True

def get_expenses():
    with session_scope() as s:
        rows = s.query(Expense).order_by(Expense.date.desc()).all()
        return [{"id": r.id, "description": r.description, "category": r.category, "amount": r.amount, "date": r.date} for r in rows]

# Inventory
def add_inventory_item(name, quantity=0.0, unit=None, cost_per_unit=0.0, low_threshold=5.0):
    with session_scope() as s:
        it = InventoryItem(name=name, quantity=quantity, unit=unit, cost_per_unit=cost_per_unit, low_threshold=low_threshold)
        s.add(it); s.flush(); return it.id

def edit_inventory_item(item_id, name, quantity, unit, cost_per_unit, low_threshold):
    with session_scope() as s:
        it = s.get(InventoryItem, item_id)
        if not it: return False
        it.name = name; it.quantity = quantity; it.unit = unit; it.cost_per_unit = cost_per_unit; it.low_threshold = low_threshold
        return True

def delete_inventory_item(item_id):
    with session_scope() as s:
        it = s.get(InventoryItem, item_id)
        if not it: return False
        s.delete(it); return True

def get_inventory_items():
    with session_scope() as s:
        rows = s.query(InventoryItem).order_by(InventoryItem.id).all()
        return [{"id": r.id, "name": r.name, "quantity": r.quantity, "unit": r.unit, "cost_per_unit": r.cost_per_unit, "low_threshold": r.low_threshold} for r in rows]

# Daily Transactions (إدخال يومي)
def add_daily_transaction(date, income, expense, notes=None):
    with session_scope() as s:
        d = DailyTransaction(date=date, income=income, expense=expense, notes=notes)
        s.add(d); s.flush(); return d.id

def get_daily_transactions():
    with session_scope() as s:
        rows = s.query(DailyTransaction).order_by(DailyTransaction.date.desc()).all()
        return [{"id": r.id, "date": r.date, "income": r.income, "expense": r.expense, "notes": r.notes} for r in rows]

# ---------------------------
# Financial summaries
# ---------------------------
def get_patient_financial_summary(patient_id):
    with session_scope() as s:
        payments = s.query(Payment).join(Appointment).filter(Appointment.patient_id == patient_id).all()
        total_amount = sum((p.total_amount or 0.0) for p in payments)
        total_paid = sum((p.paid_amount or 0.0) for p in payments)
        balance = total_amount - total_paid
        last_payment = max([p.date_paid for p in payments if p.date_paid], default=None)
        return {"total_amount": total_amount, "total_paid": total_paid, "balance": balance, "last_payment": last_payment}

def get_daily_summary(date):
    # date: datetime.date
    start = datetime.datetime.combine(date, datetime.time.min)
    end = datetime.datetime.combine(date, datetime.time.max)
    with session_scope() as s:
        payments = s.query(Payment).filter(Payment.date_paid.between(start, end)).all()
        income_from_payments = sum((p.paid_amount or 0.0) for p in payments)
        daily_entries = s.query(DailyTransaction).filter(DailyTransaction.date.between(start, end)).all()
        extra_income = sum((d.income or 0.0) for d in daily_entries)
        total_expense_from_daily = sum((d.expense or 0.0) for d in daily_entries)
        expenses = s.query(Expense).filter(Expense.date.between(start, end)).all()
        total_expenses = sum((e.amount or 0.0) for e in expenses) + total_expense_from_daily
        appointments = s.query(Appointment).filter(Appointment.date.between(start, end)).all()
        patients_count = len(set(a.patient_id for a in appointments))
        appointments_count = len(appointments)
        return {
            "income_total": income_from_payments + extra_income,
            "expense_total": total_expenses,
            "net_profit": (income_from_payments + extra_income) - total_expenses,
            "patients_count": patients_count,
            "appointments_count": appointments_count
        }

def get_monthly_financials(year, month):
    # returns aggregated daily totals for that month
    start = datetime.datetime(year, month, 1)
    if month == 12:
        end = datetime.datetime(year+1, 1, 1) - datetime.timedelta(seconds=1)
    else:
        end = datetime.datetime(year, month+1, 1) - datetime.timedelta(seconds=1)
    with session_scope() as s:
        payments = s.query(Payment).filter(Payment.date_paid.between(start, end)).all()
        expenses = s.query(Expense).filter(Expense.date.between(start, end)).all()
        daily = s.query(DailyTransaction).filter(DailyTransaction.date.between(start, end)).all()
        # group by date
        recs = {}
        for p in payments:
            d = p.date_paid.date() if p.date_paid else None
            if d:
                recs.setdefault(d, {"income":0.0, "expense":0.0})
                recs[d]["income"] += (p.paid_amount or 0.0)
        for e in expenses:
            d = e.date.date() if e.date else None
            if d:
                recs.setdefault(d, {"income":0.0, "expense":0.0})
                recs[d]["expense"] += (e.amount or 0.0)
        for dtx in daily:
            d = dtx.date.date() if dtx.date else None
            if d:
                recs.setdefault(d, {"income":0.0, "expense":0.0})
                recs[d]["income"] += (dtx.income or 0.0)
                recs[d]["expense"] += (dtx.expense or 0.0)
        # produce sorted lists
        dates = sorted(recs.keys())
        rows = [{"date": d, "income": recs[d]["income"], "expense": recs[d]["expense"], "net": recs[d]["income"]-recs[d]["expense"]} for d in dates]
        return rows

# ---------------------------
# UI: CSS and header
# ---------------------------
def local_css():
    st.markdown(
        """
        <style>
        /* theme-like */
        .sidebar .sidebar-content {background: linear-gradient(#0f1724, #0b1220);}
        .stApp { background: linear-gradient(#ffffff, #f5f7fb); }
        header {display:none;}
        .topbar {padding:10px; border-radius:6px; background:linear-gradient(90deg,#0ea5b3,#0369a1); color:white; margin-bottom:10px;}
        .metric-box {background:white; padding:10px; border-radius:8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);}
        .low-stock {color: #b91c1c; font-weight:700;}
        .ok-stock {color: #166534; font-weight:700;}
        </style>
        """, unsafe_allow_html=True
    )

def app_header():
    st.markdown(f"""
        <div class="topbar">
            <h2 style="margin:0">🦷 نظام إدارة عيادة الأسنان — لوحة التحكم المالية</h2>
            <div style="font-size:13px; opacity:0.9">إدارة المرضى • المواعيد • الحسابات • التقارير</div>
        </div>
    """, unsafe_allow_html=True)

# ---------------------------
# Pages
# ---------------------------
def dashboard_page():
    st.header("لوحة التحكم الرئيسية")
    today = datetime.date.today()
    summary = get_daily_summary(today)
    patients = get_patients()
    appointments = get_appointments()
    # quick metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("المرضى الكلّي", len(patients))
    col2.metric("مواعيد اليوم", summary["appointments_count"])
    col3.metric("دخل اليوم", f"{summary['income_total']:.2f}")
    col4.metric("مصروف اليوم", f"{summary['expense_total']:.2f}")
    st.markdown("---")
    st.subheader("الرسم البياني الشهري (إجمالي يومي)")
    now = datetime.datetime.now()
    rows = get_monthly_financials(now.year, now.month)
    if rows:
        dfm = pd.DataFrame(rows)
        fig = px.line(dfm, x="date", y=["income", "expense", "net"], labels={"value":"المبلغ","variable":"البند"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد بيانات لهذا الشهر بعد.")
    st.markdown("---")
    st.subheader("تنبيهات المخزون المنخفض")
    items = get_inventory_items()
    low = [it for it in items if it["quantity"] is not None and it["quantity"] <= (it["low_threshold"] or 0)]
    if low:
        for it in low:
            st.markdown(f"- <span class='low-stock'>{it['name']}</span>: الكمية الحالية {it['quantity']} {it['unit'] or ''}", unsafe_allow_html=True)
    else:
        st.success("جميع البنود بكميات كافية")

# Patients page
def patients_page():
    st.header("إدارة المرضى")
    with st.expander("➕ إضافة مريض جديد", expanded=False):
        with st.form("add_patient"):
            c1, c2, c3 = st.columns(3)
            with c1:
                name = st.text_input("الاسم")
                age = st.number_input("العمر", min_value=0, value=0)
            with c2:
                gender = st.selectbox("الجنس", ["", "ذكر", "أنثى"])
                phone = st.text_input("الهاتف")
            with c3:
                address = st.text_input("العنوان")
                image = st.file_uploader("رفع صورة (اختياري)", type=["png","jpg","jpeg"])
            medical_history = st.text_area("التاريخ الطبي")
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("الاسم مطلوب")
                else:
                    pid = add_patient(name=name.strip(), age=int(age), gender=gender or None, phone=phone or None, address=address or None, medical_history=medical_history or None, image=image)
                    st.success(f"تمت إضافة المريض (ID: {pid})")
    st.markdown("---")
    patients = get_patients()
    df = pd.DataFrame(patients) if patients else pd.DataFrame(columns=["id","name","age","gender","phone","address"])
    search = st.text_input("بحث (الاسم/الهاتف/العنوان)")
    if search:
        df = df[df.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)]
    st.dataframe(df, use_container_width=True)
    st.markdown("### تفاصيل المريض وملف الحساب المالي")
    ids = [r["id"] for r in patients]
    sel = st.selectbox("اختر ID المريض", options=[""] + ids)
    if sel:
        pid = int(sel)
        p = next((x for x in patients if x["id"] == pid), None)
        if p:
            st.subheader(f"ملف {p['name']}")
            st.write(f"العمر: {p['age']} — الجنس: {p['gender']} — الهاتف: {p['phone']}")
            st.write("التاريخ الطبي:")
            st.write(p["medical_history"] or "-")
            # financial summary
            fin = get_patient_financial_summary(pid)
            st.markdown("**الملف المالي**")
            st.metric("إجمالي الفواتير", f"{fin['total_amount']:.2f}")
            st.metric("المبلغ المدفوع", f"{fin['total_paid']:.2f}")
            st.metric("المتبقي (دين)", f"{fin['balance']:.2f}")
            st.write(f"آخر دفعة: {fin['last_payment'] if fin['last_payment'] else '-'}")
            # appointment history
            st.markdown("**سجل المواعيد للمريض**")
            appts = [a for a in get_appointments() if a["patient_id"] == pid]
            if appts:
                st.dataframe(pd.DataFrame(appts), use_container_width=True)
            else:
                st.info("لا توجد مواعيد لهذا المريض بعد.")
            # edit / delete
            if st.button("حذف المريض"):
                if delete_patient(pid):
                    st.success("تم الحذف")
                else:
                    st.error("حدث خطأ")

# Doctors page
def doctors_page_ui():
    st.header("إدارة الأطباء")
    with st.expander("إضافة طبيب جديد", expanded=False):
        with st.form("add_doc"):
            name = st.text_input("الاسم")
            specialty = st.text_input("التخصص")
            phone = st.text_input("الهاتف")
            email = st.text_input("البريد الإلكتروني")
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("الاسم مطلوب")
                else:
                    did = add_doctor(name=name.strip(), specialty=specialty or None, phone=phone or None, email=email or None)
                    st.success(f"تمت الإضافة (ID: {did})")
    st.markdown("---")
    doctors = get_doctors()
    df = pd.DataFrame(doctors) if doctors else pd.DataFrame(columns=["id","name","specialty","phone","email"])
    st.dataframe(df, use_container_width=True)

# Treatments page
def treatments_page_ui():
    st.header("إدارة العلاجات")
    with st.expander("إضافة علاج", expanded=False):
        with st.form("add_treat"):
            name = st.text_input("اسم العلاج")
            base_cost = st.number_input("السعر الأساسي", min_value=0.0, value=0.0)
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("الاسم مطلوب")
                else:
                    tid = add_treatment(name=name.strip(), base_cost=float(base_cost))
                    st.success(f"تمت الإضافة (ID: {tid})")
    st.markdown("---")
    treatments = get_treatments()
    df = pd.DataFrame(treatments) if treatments else pd.DataFrame(columns=["id","name","base_cost"])
    st.dataframe(df, use_container_width=True)

    st.markdown("### إعداد نسب التوزيع")
    doctors = get_doctors()
    if doctors and treatments:
        with st.form("set_tp"):
            t_opts = [(f"{t['id']} - {t['name']}", t['id']) for t in treatments]
            d_opts = [(f"{d['id']} - {d['name']}", d['id']) for d in doctors]
            t_choice = st.selectbox("اختر علاج", options=[("",None)] + t_opts, format_func=lambda x: x[0] if x else "")
            d_choice = st.selectbox("اختر طبيب", options=[("",None)] + d_opts, format_func=lambda x: x[0] if x else "")
            clinic_perc = st.number_input("نسبة العيادة (%)", min_value=0.0, max_value=100.0, value=50.0)
            doctor_perc = st.number_input("نسبة الطبيب (%)", min_value=0.0, max_value=100.0, value=50.0)
            if st.form_submit_button("حفظ"):
                if not (t_choice and d_choice and t_choice[1] and d_choice[1]):
                    st.error("اختر علاجًا وطبيبًا")
                else:
                    set_treatment_percentage(t_choice[1], d_choice[1], float(clinic_perc), float(doctor_perc))
                    st.success("تم الحفظ")
    else:
        st.info("أضف طبيبًا وعلاجًا لتعيين النسب")

    st.markdown("### قائمة نسب التوزيع")
    tps = get_treatment_percentages()
    st.dataframe(pd.DataFrame(tps) if tps else pd.DataFrame(), use_container_width=True)

# Appointments page
def appointments_page_ui():
    st.header("إدارة المواعيد")
    patients = get_patients(); doctors = get_doctors(); treatments = get_treatments()
    with st.expander("حجز موعد جديد", expanded=False):
        with st.form("add_appt"):
            p_opts = [(f"{p['id']} - {p['name']}", p['id']) for p in patients]
            d_opts = [(f"{d['id']} - {d['name']}", d['id']) for d in doctors]
            t_opts = [(f"{t['id']} - {t['name']}", t['id']) for t in treatments]
            p_choice = st.selectbox("المريض", options=[("",None)] + p_opts, format_func=lambda x: x[0] if x else "")
            d_choice = st.selectbox("الطبيب", options=[("",None)] + d_opts, format_func=lambda x: x[0] if x else "")
            t_choice = st.selectbox("العلاج", options=[("",None)] + t_opts, format_func=lambda x: x[0] if x else "")
            date = datetime_input("تاريخ ووقت الموعد", value=datetime.datetime.now() + datetime.timedelta(days=1))
            notes = st.text_area("ملاحظات")
            if st.form_submit_button("حجز"):
                if not (p_choice and d_choice and t_choice and p_choice[1] and d_choice[1] and t_choice[1]):
                    st.error("اختر مريضًا وطبيبًا وعلاجًا")
                else:
                    aid = add_appointment(patient_id=p_choice[1], doctor_id=d_choice[1], treatment_id=t_choice[1], date=date, status="مجدول", notes=notes)
                    st.success(f"تم حجز الموعد (ID: {aid})")
    st.markdown("---")
    appts = get_appointments()
    df = pd.DataFrame(appts) if appts else pd.DataFrame(columns=["id","patient_name","doctor_name","treatment_name","date","status"])
    st.dataframe(df, use_container_width=True)

# Payments page
def payments_page_ui():
    st.header("الدفعات والفواتير")
    appts = get_appointments()
    payments = get_payments()
    with st.expander("تسجيل دفعة", expanded=False):
        with st.form("add_pay"):
            appt_opts = [(f"{a['id']} - {a['patient_name']}", a['id']) for a in appts]
            appt_choice = st.selectbox("اختر موعد (اختياري)", options=[("",None)] + appt_opts, format_func=lambda x: x[0] if x else "")
            total_amount = st.number_input("المبلغ الإجمالي", min_value=0.0, value=0.0)
            discounts = st.number_input("الخصم", min_value=0.0, value=0.0)
            taxes = st.number_input("الضرائب", min_value=0.0, value=0.0)
            paid_amount = st.number_input("المبلغ المدفوع", min_value=0.0, value=0.0)
            payment_method = st.selectbox("طريقة الدفع", ["نقدًا", "بطاقة", "تحويل بنكي", "أخرى"])
            if st.form_submit_button("تسجيل الدفعة"):
                appt_id = appt_choice[1] if appt_choice else None
                pid = add_payment(appointment_id=appt_id, total_amount=float(total_amount), paid_amount=float(paid_amount), payment_method=payment_method, discounts=float(discounts), taxes=float(taxes))
                st.success(f"تم تسجيل الدفعة (ID: {pid})")
    st.markdown("---")
    df = pd.DataFrame(payments) if payments else pd.DataFrame(columns=["id","date_paid","total_amount","paid_amount"])
    st.dataframe(df, use_container_width=True)
    st.markdown("طباعة فاتورة")
    ids = [r["id"] for r in payments]
    sel = st.selectbox("اختر دفعة للطباعة", options=[""]+ids)
    if sel:
        buf = generate_invoice_pdf_buffer(payment_id=int(sel))
        st.download_button("تحميل PDF الفاتورة", data=buf, file_name=f"invoice_{sel}.pdf", mime="application/pdf")

# Expenses page
def expenses_page_ui():
    st.header("المصروفات")
    with st.expander("إضافة مصروف", expanded=False):
        with st.form("add_exp"):
            desc = st.text_input("البيان")
            category = st.text_input("التصنيف")
            amount = st.number_input("المبلغ", min_value=0.0, value=0.0)
            date = st.date_input("التاريخ", value=datetime.date.today())
            if st.form_submit_button("حفظ"):
                add_expense(description=desc or None, category=category or None, amount=float(amount), date=datetime.datetime.combine(date, datetime.datetime.min.time()))
                st.success("تم الحفظ")
    st.markdown("---")
    exps = get_expenses()
    st.dataframe(pd.DataFrame(exps) if exps else pd.DataFrame(columns=["id","description","category","amount","date"]), use_container_width=True)

# Inventory page
def inventory_page_ui():
    st.header("إدارة المخزون")
    with st.expander("إضافة بند مخزون", expanded=False):
        with st.form("add_item"):
            name = st.text_input("اسم الصنف")
            quantity = st.number_input("الكمية", min_value=0.0, value=0.0)
            unit = st.text_input("الوحدة")
            cost = st.number_input("تكلفة الوحدة", min_value=0.0, value=0.0)
            low = st.number_input("حد التنبيه (Low threshold)", min_value=0.0, value=5.0)
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("أدخل اسم الصنف")
                else:
                    iid = add_inventory_item(name=name.strip(), quantity=float(quantity), unit=unit or None, cost_per_unit=float(cost), low_threshold=float(low))
                    st.success(f"تمت الإضافة (ID: {iid})")
    st.markdown("---")
    items = get_inventory_items()
    df = pd.DataFrame(items) if items else pd.DataFrame(columns=["id","name","quantity","unit","cost_per_unit","low_threshold"])
    st.dataframe(df, use_container_width=True)

# Daily Entry page
def daily_entry_ui():
    st.header("الإدخال اليومي")
    with st.form("daily_form"):
        date = st.date_input("التاريخ", value=datetime.date.today())
        income = st.number_input("دخل إضافي اليوم", min_value=0.0, value=0.0)
        expense = st.number_input("مصروف إضافي اليوم", min_value=0.0, value=0.0)
        notes = st.text_area("ملاحظات")
        if st.form_submit_button("حفظ الإدخال اليومي"):
            dt = datetime.datetime.combine(date, datetime.datetime.min.time())
            add_daily_transaction(date=dt, income=float(income), expense=float(expense), notes=notes or None)
            st.success("تم الحفظ")
    st.markdown("---")
    st.subheader("سجل الإدخالات اليومية")
    rows = get_daily_transactions()
    st.dataframe(pd.DataFrame(rows) if rows else pd.DataFrame(columns=["id","date","income","expense","notes"]), use_container_width=True)

# Daily summary page
def daily_summary_ui():
    st.header("الملخّص اليومي المالي")
    sel_date = st.date_input("اختر اليوم", value=datetime.date.today())
    summary = get_daily_summary(sel_date)
    st.metric("إجمالي الدخل", f"{summary['income_total']:.2f}")
    st.metric("إجمالي المصروف", f"{summary['expense_total']:.2f}")
    st.metric("صافي الربح", f"{summary['net_profit']:.2f}")
    st.write(f"عدد المرضى اليوم: {summary['patients_count']}")
    st.write(f"عدد المواعيد اليوم: {summary['appointments_count']}")
    # export
    with st.expander("تصدير التقرير"):
        df_payments = pd.DataFrame([p for p in get_payments() if p["date_paid"] and p["date_paid"].date() == sel_date])
        df_expenses = pd.DataFrame([e for e in get_expenses() if e["date"] and e["date"].date() == sel_date])
        # combine for excel
        if st.button("تحميل تقرير اليوم (Excel)"):
            writer_buf = io.BytesIO()
            with pd.ExcelWriter(writer_buf, engine="openpyxl") as writer:
                df_payments.to_excel(writer, sheet_name="payments", index=False)
                df_expenses.to_excel(writer, sheet_name="expenses", index=False)
            writer_buf.seek(0)
            st.download_button("تحميل ملف Excel", data=writer_buf, file_name=f"daily_report_{sel_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Reports page
def reports_ui():
    st.header("التقارير")
    st.subheader("تقرير شهري")
    col1, col2 = st.columns(2)
    with col1:
        y = st.number_input("السنة", min_value=2000, max_value=2100, value=datetime.date.today().year, step=1)
    with col2:
        m = st.number_input("الشهر (1-12)", min_value=1, max_value=12, value=datetime.date.today().month, step=1)
    rows = get_monthly_financials(int(y), int(m))
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        fig = px.bar(df, x="date", y=["income", "expense", "net"], title=f"التقارير الشهرية {y}-{m}")
        st.plotly_chart(fig, use_container_width=True)
        # export
        if st.button("تصدير تقرير الشهر (Excel)"):
            bytes_excel = df_to_excel_bytes(df)
            st.download_button("تحميل Excel", data=bytes_excel, file_name=f"monthly_report_{y}_{m}.xlsx")
    else:
        st.info("لا توجد بيانات لهذا الشهر")

# ---------------------------
# Main
# ---------------------------
def main():
    st.set_page_config(page_title="نظام إدارة عيادة الأسنان - كامل", layout="wide", page_icon="🦷")
    local_css()
    app_header()

    # Sidebar menu (optionally prettier with option_menu)
    if HAS_OPTION_MENU:
        choice = option_menu(None, ["لوحة التحكم", "المرضى", "الأطباء", "العلاجات", "المواعيد", "الدفعات", "المصروفات", "المخزون", "الإدخال اليومي", "الملخص اليومي", "التقارير"],
                             icons=["speedometer","people","person-badge","stethoscope","calendar-check","credit-card","cash","box-seam","calendar-day","list-task","file-earmark-bar-graph"],
                             menu_icon="cast", default_index=0, orientation="vertical")
    else:
        choice = st.sidebar.selectbox("القسم", ["لوحة التحكم", "المرضى", "الأطباء", "العلاجات", "المواعيد", "الدفعات", "المصروفات", "المخزون", "الإدخال اليومي", "الملخص اليومي", "التقارير"])

    # Route pages
    if choice == "لوحة التحكم":
        dashboard_page()
    elif choice == "المرضى":
        patients_page()
    elif choice == "الأطباء":
        doctors_page_ui()
    elif choice == "العلاجات":
        treatments_page_ui()
    elif choice == "المواعيد":
        appointments_page_ui()
    elif choice == "الدفعات":
        payments_page_ui()
    elif choice == "المصروفات":
        expenses_page_ui()
    elif choice == "المخزون":
        inventory_page_ui()
    elif choice == "الإدخال اليومي":
        daily_entry_ui()
    elif choice == "الملخص اليومي":
        daily_summary_ui()
    elif choice == "التقارير":
        reports_ui()
    else:
        st.write("اختر صفحة من القائمة")

if __name__ == "__main__":
    main()
