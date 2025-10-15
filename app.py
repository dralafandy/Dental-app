# dental_clinic_v2.py
# نظام إدارة عيادة أسنان متكامل - واجهة بيضاء - عملة: جنيه مصري
# حفظ الملف كنص أولاً (dental_clinic_v2.txt) ثم أعد تسميته إلى dental_clinic_v2.py للتشغيل
# تشغيل: streamlit run dental_clinic_v2.py

import streamlit as st
import pandas as pd
import datetime
import os
import io
import uuid
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import plotly.express as px

# ---------------------------
# Configuration
# ---------------------------
DB_URI = "sqlite:///dental_clinic.db"
IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)

CURRENCY_NAME = "جنيه مصري"
CURRENCY_SYMBOL = "جنيه"

# ---------------------------
# Database setup
# ---------------------------
engine = create_engine(DB_URI, echo=False, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()

# ---------------------------
# Models (including suppliers & daily summary)
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

class DailySummary(Base):
    __tablename__ = "daily_summaries"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.datetime.now)
    total_income = Column(Float, default=0.0)
    clinic_income = Column(Float, default=0.0)
    doctor_income = Column(Float, default=0.0)
    total_expenses = Column(Float, default=0.0)
    net_profit = Column(Float, default=0.0)
    notes = Column(Text)

# Suppliers & invoices
class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String)  # "خامات" أو "معمل" أو "خدمات"
    phone = Column(String)
    address = Column(String)
    balance = Column(Float, default=0.0)
    notes = Column(Text)
    transactions = relationship("SupplierTransaction", back_populates="supplier", cascade="all, delete-orphan")
    invoices = relationship("SupplierInvoice", back_populates="supplier", cascade="all, delete-orphan")

class SupplierTransaction(Base):
    __tablename__ = "supplier_transactions"
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    date = Column(DateTime, default=datetime.datetime.now)
    description = Column(String)
    amount = Column(Float)  # موجب للمورد (دفعنا له) أو سالب (مستحق علينا)
    payment_method = Column(String)
    supplier = relationship("Supplier", back_populates="transactions")

class SupplierInvoice(Base):
    __tablename__ = "supplier_invoices"
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    invoice_no = Column(String)
    date = Column(DateTime, default=datetime.datetime.now)
    amount = Column(Float)
    paid = Column(Boolean, default=False)
    description = Column(Text)
    supplier = relationship("Supplier", back_populates="invoices")

Base.metadata.create_all(engine)

# ---------------------------
# Session helper
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
    date_part = st.date_input(f"{label} - التاريخ", value=default.date())
    time_part = st.time_input(f"{label} - الوقت", value=default.time())
    return datetime.datetime.combine(date_part, time_part)

def df_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
        writer.save()
    output.seek(0)
    return output.getvalue()

def format_money(x):
    try:
        return f"{float(x):,.2f} {CURRENCY_SYMBOL}"
    except Exception:
        return f"0.00 {CURRENCY_SYMBOL}"

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
                c.drawString(50, y, f"المبلغ الإجمالي: {p.total_amount or 0.0} {CURRENCY_SYMBOL}")
                y -= 15
                c.drawString(50, y, f"الخصم: {p.discounts or 0.0} {CURRENCY_SYMBOL}")
                y -= 15
                c.drawString(50, y, f"الضريبة: {p.taxes or 0.0} {CURRENCY_SYMBOL}")
                y -= 15
                c.drawString(50, y, f"حصة العيادة: {p.clinic_share or 0.0} {CURRENCY_SYMBOL}")
                y -= 15
                c.drawString(50, y, f"حصة الطبيب: {p.doctor_share or 0.0} {CURRENCY_SYMBOL}")
                y -= 15
                c.drawString(50, y, f"المدفوع: {p.paid_amount or 0.0} {CURRENCY_SYMBOL}")
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
# Core CRUD + Safe GETs (return dicts)
# ---------------------------

# Patients
def add_patient(name, age=None, gender=None, phone=None, address=None, medical_history=None, image=None):
    with session_scope() as s:
        p = Patient(name=name, age=age, gender=gender, phone=phone, address=address, medical_history=medical_history)
        if image:
            p.image_path = save_uploaded_image(image, prefix="patient")
        s.add(p); s.flush(); return p.id

def edit_patient(patient_id, name, age, gender, phone, address, medical_history, image=None):
    with session_scope() as s:
        p = s.get(Patient, patient_id)
        if not p: return False
        p.name = name; p.age = age; p.gender = gender; p.phone = phone; p.address = address; p.medical_history = medical_history
        if image:
            p.image_path = save_uploaded_image(image, prefix="patient")
        return True

def delete_patient(patient_id):
    with session_scope() as s:
        p = s.get(Patient, patient_id)
        if not p: return False
        s.delete(p); return True

def get_patients():
    with session_scope() as s:
        rows = s.query(Patient).order_by(Patient.id).all()
        data = []
        for r in rows:
            data.append({
                "id": r.id, "name": r.name, "age": r.age, "gender": r.gender,
                "phone": r.phone, "address": r.address, "medical_history": r.medical_history,
                "image_path": r.image_path
            })
        return data

# Doctors
def add_doctor(name, specialty=None, phone=None, email=None):
    with session_scope() as s:
        d = Doctor(name=name, specialty=specialty, phone=phone, email=email); s.add(d); s.flush(); return d.id

def edit_doctor(doctor_id, name, specialty, phone, email):
    with session_scope() as s:
        d = s.get(Doctor, doctor_id)
        if not d: return False
        d.name = name; d.specialty = specialty; d.phone = phone; d.email = email; return True

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
                    clinic_share=clinic_share, doctor_share=doctor_share, payment_method=payment_method,
                    discounts=discounts, taxes=taxes, date_paid=datetime.datetime.now())
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
        it.name = name; it.quantity = quantity; it.unit = unit; it.cost_per_unit = cost_per_unit; it.low_threshold = low_threshold; return True

def delete_inventory_item(item_id):
    with session_scope() as s:
        it = s.get(InventoryItem, item_id)
        if not it: return False
        s.delete(it); return True

def get_inventory_items():
    with session_scope() as s:
        rows = s.query(InventoryItem).order_by(InventoryItem.id).all()
        return [{"id": r.id, "name": r.name, "quantity": r.quantity, "unit": r.unit, "cost_per_unit": r.cost_per_unit, "low_threshold": r.low_threshold} for r in rows]

# Daily transactions & summaries
def add_daily_transaction(date, income, expense, notes=None):
    with session_scope() as s:
        d = DailyTransaction(date=date, income=income, expense=expense, notes=notes)
        s.add(d); s.flush(); return d.id

def get_daily_transactions():
    with session_scope() as s:
        rows = s.query(DailyTransaction).order_by(DailyTransaction.date.desc()).all()
        return [{"id": r.id, "date": r.date, "income": r.income, "expense": r.expense, "notes": r.notes} for r in rows]

def add_daily_summary(date, total_income, clinic_income, doctor_income, total_expenses, net_profit, notes=None):
    with session_scope() as s:
        d = DailySummary(date=date, total_income=total_income, clinic_income=clinic_income, doctor_income=doctor_income, total_expenses=total_expenses, net_profit=net_profit, notes=notes)
        s.add(d); s.flush(); return d.id

def get_daily_summaries():
    with session_scope() as s:
        rows = s.query(DailySummary).order_by(DailySummary.date.desc()).all()
        return [{"id": r.id, "date": r.date, "total_income": r.total_income, "clinic_income": r.clinic_income, "doctor_income": r.doctor_income, "total_expenses": r.total_expenses, "net_profit": r.net_profit, "notes": r.notes} for r in rows]

# Suppliers & invoices & transactions
def add_supplier(name, category=None, phone=None, address=None, notes=None):
    with session_scope() as s:
        sup = Supplier(name=name, category=category, phone=phone, address=address, notes=notes)
        s.add(sup); s.flush(); return sup.id

def edit_supplier(supplier_id, name, category, phone, address, notes):
    with session_scope() as s:
        sup = s.get(Supplier, supplier_id)
        if not sup: return False
        sup.name = name; sup.category = category; sup.phone = phone; sup.address = address; sup.notes = notes; return True

def delete_supplier(supplier_id):
    with session_scope() as s:
        sup = s.get(Supplier, supplier_id)
        if not sup: return False
        s.delete(sup); return True

def get_suppliers():
    with session_scope() as s:
        rows = s.query(Supplier).order_by(Supplier.id).all()
        return [{"id": r.id, "name": r.name, "category": r.category, "phone": r.phone, "address": r.address, "balance": r.balance, "notes": r.notes} for r in rows]

def add_supplier_transaction(supplier_id, description, amount, payment_method):
    with session_scope() as s:
        tr = SupplierTransaction(supplier_id=supplier_id, description=description, amount=amount, payment_method=payment_method, date=datetime.datetime.now())
        s.add(tr)
        sup = s.get(Supplier, supplier_id)
        if sup:
            sup.balance = (sup.balance or 0.0) + (amount or 0.0)
        s.flush(); return tr.id

def get_supplier_transactions(supplier_id):
    with session_scope() as s:
        rows = s.query(SupplierTransaction).filter_by(supplier_id=supplier_id).order_by(SupplierTransaction.date.desc()).all()
        return [{"id": r.id, "date": r.date, "description": r.description, "amount": r.amount, "payment_method": r.payment_method} for r in rows]

def add_supplier_invoice(supplier_id, invoice_no, amount, description=None, date=None, paid=False):
    if date is None: date = datetime.datetime.now()
    with session_scope() as s:
        inv = SupplierInvoice(supplier_id=supplier_id, invoice_no=invoice_no, amount=amount, description=description, date=date, paid=paid)
        s.add(inv)
        # add to supplier balance as debt (positive means we owe supplier)
        sup = s.get(Supplier, supplier_id)
        if sup:
            sup.balance = (sup.balance or 0.0) + (amount or 0.0)
        s.flush(); return inv.id

def get_supplier_invoices(supplier_id):
    with session_scope() as s:
        rows = s.query(SupplierInvoice).filter_by(supplier_id=supplier_id).order_by(SupplierInvoice.date.desc()).all()
        return [{"id": r.id, "invoice_no": r.invoice_no, "date": r.date, "amount": r.amount, "paid": r.paid, "description": r.description} for r in rows]

# ---------------------------
# Financial summaries & reports
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
        # compute clinic/doctor shares from payments for accuracy
        clinic_income_from_payments = sum((p.clinic_share or 0.0) for p in payments)
        doctor_income_from_payments = sum((p.doctor_share or 0.0) for p in payments)
        daily_entries = s.query(DailyTransaction).filter(DailyTransaction.date.between(start, end)).all()
        extra_income = sum((d.income or 0.0) for d in daily_entries)
        total_expense_from_daily = sum((d.expense or 0.0) for d in daily_entries)
        expenses = s.query(Expense).filter(Expense.date.between(start, end)).all()
        total_expenses = sum((e.amount or 0.0) for e in expenses) + total_expense_from_daily
        # appointments count and unique patients
        appointments = s.query(Appointment).filter(Appointment.date.between(start, end)).all()
        patients_count = len(set(a.patient_id for a in appointments))
        appointments_count = len(appointments)
        # final sums
        total_income = income_from_payments + extra_income
        clinic_income = clinic_income_from_payments  # plus any clinic-specific extra incomes if needed
        doctor_income = doctor_income_from_payments
        net_profit = clinic_income - total_expenses
        return {
            "income_total": total_income,
            "clinic_income": clinic_income,
            "doctor_income": doctor_income,
            "expense_total": total_expenses,
            "net_profit": net_profit,
            "patients_count": patients_count,
            "appointments_count": appointments_count
        }

def get_monthly_financials(year, month):
    start = datetime.datetime(year, month, 1)
    if month == 12:
        end = datetime.datetime(year+1, 1, 1) - datetime.timedelta(seconds=1)
    else:
        end = datetime.datetime(year, month+1, 1) - datetime.timedelta(seconds=1)
    with session_scope() as s:
        payments = s.query(Payment).filter(Payment.date_paid.between(start, end)).all()
        expenses = s.query(Expense).filter(Expense.date.between(start, end)).all()
        daily = s.query(DailyTransaction).filter(DailyTransaction.date.between(start, end)).all()
        recs = {}
        for p in payments:
            d = p.date_paid.date() if p.date_paid else None
            if d:
                recs.setdefault(d, {"income":0.0, "expense":0.0, "clinic":0.0, "doctor":0.0})
                recs[d]["income"] += (p.paid_amount or 0.0)
                recs[d]["clinic"] += (p.clinic_share or 0.0)
                recs[d]["doctor"] += (p.doctor_share or 0.0)
        for e in expenses:
            d = e.date.date() if e.date else None
            if d:
                recs.setdefault(d, {"income":0.0, "expense":0.0, "clinic":0.0, "doctor":0.0})
                recs[d]["expense"] += (e.amount or 0.0)
        for dtx in daily:
            d = dtx.date.date() if dtx.date else None
            if d:
                recs.setdefault(d, {"income":0.0, "expense":0.0, "clinic":0.0, "doctor":0.0})
                recs[d]["income"] += (dtx.income or 0.0)
                recs[d]["expense"] += (dtx.expense or 0.0)
        dates = sorted(recs.keys())
        rows = [{"date": d, "income": recs[d]["income"], "expense": recs[d]["expense"], "clinic": recs[d]["clinic"], "doctor": recs[d]["doctor"], "net": recs[d]["income"]-recs[d]["expense"]} for d in dates]
        return rows

# ---------------------------
# UI Styling (white theme)
# ---------------------------
def local_css_white():
    st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #000000; }
    body, p, label, span, div { color: #000000 !important; }
    .block-container { padding-top: 1rem; background-color: #ffffff; }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stNumberInput>div>div>input { background-color:#ffffff !important; color:#000000 !important; border:1px solid #ddd !important; }
    .stButton>button { background-color:#0b63b6 !important; color:white !important; border-radius:6px !important; }
    .stDownloadButton>button { background-color:#0b63b6 !important; color:white !important; border-radius:6px !important; }
    .stDataFrame table { background-color: #ffffff !important; color:#000000 !important; }
    .topbar { padding:10px; border-radius:6px; background:#ffffff; color:#000000; margin-bottom:8px; border:1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

def app_header_white():
    st.markdown(f"""
        <div class="topbar">
            <h2 style="margin:0">🦷 نظام إدارة عيادة الأسنان</h2>
            <div style="font-size:13px; opacity:0.8">{CURRENCY_NAME} — إدارة المرضى، الحسابات، الموردين والتقارير</div>
        </div>
    """, unsafe_allow_html=True)

# ---------------------------
# Pages (Dashboard + CRUD + Financials + Suppliers)
# ---------------------------

def dashboard_page():
    st.header("لوحة التحكم")
    today = datetime.date.today()
    summary = get_daily_summary(today)
    patients = get_patients(); appointments = get_appointments()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("المرضى الكلّي", len(patients))
    c2.metric("مواعيد اليوم", summary["appointments_count"])
    c3.metric("دخل اليوم", format_money(summary["income_total"]))
    c4.metric("مصروف اليوم", format_money(summary["expense_total"]))
    st.markdown("---")
    st.subheader("الرسم البياني الشهري")
    now = datetime.datetime.now()
    rows = get_monthly_financials(now.year, now.month)
    if rows:
        dfm = pd.DataFrame(rows)
        fig = px.line(dfm, x="date", y=["income","expense","net"], labels={"value":"المبلغ","variable":"البند"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد بيانات هذا الشهر")
    st.markdown("---")
    st.subheader("تنبيهات المخزون")
    items = get_inventory_items()
    low = [it for it in items if it["quantity"] is not None and it["quantity"] <= (it["low_threshold"] or 0)]
    if low:
        for it in low:
            st.markdown(f"- **{it['name']}**: الكمية الحالية {it['quantity']} {it['unit'] or ''}")
    else:
        st.success("جميع العناصر بكميات كافية")

def patients_page_ui():
    st.header("إدارة المرضى")
    with st.expander("إضافة مريض جديد", expanded=False):
        with st.form("add_patient"):
            col1,col2,col3 = st.columns(3)
            with col1:
                name = st.text_input("الاسم")
                age = st.number_input("العمر", min_value=0, value=0)
            with col2:
                gender = st.selectbox("الجنس", ["", "ذكر", "أنثى"])
                phone = st.text_input("الهاتف")
            with col3:
                address = st.text_input("العنوان")
                image = st.file_uploader("رفع صورة (اختياري)", type=["png","jpg","jpeg"])
            medical_history = st.text_area("التاريخ الطبي")
            if st.form_submit_button("إضافة"):
                if not name.strip(): st.error("الاسم مطلوب")
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
    st.markdown("### تفاصيل المريض")
    ids = [r["id"] for r in patients]
    sel = st.selectbox("اختر ID المريض", options=[""] + ids)
    if sel:
        pid = int(sel)
        p = next((x for x in patients if x["id"] == pid), None)
        if p:
            st.subheader(f"{p['name']}")
            st.write(f"العمر: {p['age']} — الجنس: {p['gender'] or '-'} — الهاتف: {p['phone'] or '-'}")
            st.write("التاريخ الطبي:"); st.write(p["medical_history"] or "-")
            fin = get_patient_financial_summary(pid)
            st.markdown("**الملف المالي**")
            st.metric("إجمالي الفواتير", format_money(fin["total_amount"]))
            st.metric("المدفوع", format_money(fin["total_paid"]))
            st.metric("المتبقي (دين)", format_money(fin["balance"]))
            st.write(f"آخر دفعة: {fin['last_payment'] if fin['last_payment'] else '-'}")
            st.markdown("سجل المواعيد:")
            appts = [a for a in get_appointments() if a["patient_id"] == pid]
            if appts: st.dataframe(pd.DataFrame(appts), use_container_width=True)
            else: st.info("لا توجد مواعيد")
            if st.button("حذف المريض"):
                ok = delete_patient(pid)
                if ok: st.success("تم الحذف"); st.experimental_rerun()
                else: st.error("فشل الحذف")

def doctors_page_ui():
    st.header("إدارة الأطباء")
    with st.expander("إضافة طبيب جديد", expanded=False):
        with st.form("add_doc"):
            name = st.text_input("الاسم"); specialty = st.text_input("التخصص")
            phone = st.text_input("الهاتف"); email = st.text_input("البريد الإلكتروني")
            if st.form_submit_button("إضافة"):
                if not name.strip(): st.error("الاسم مطلوب")
                else:
                    did = add_doctor(name=name.strip(), specialty=specialty or None, phone=phone or None, email=email or None)
                    st.success(f"تمت الإضافة (ID: {did})")
    st.markdown("---")
    docs = get_doctors()
    st.dataframe(pd.DataFrame(docs) if docs else pd.DataFrame(columns=["id","name","specialty","phone","email"]), use_container_width=True)

def treatments_page_ui():
    st.header("إدارة العلاجات")
    with st.expander("إضافة علاج", expanded=False):
        with st.form("add_treat"):
            name = st.text_input("اسم العلاج"); base_cost = st.number_input("السعر الأساسي", min_value=0.0, value=0.0)
            if st.form_submit_button("إضافة"):
                if not name.strip(): st.error("الاسم مطلوب")
                else:
                    tid = add_treatment(name=name.strip(), base_cost=float(base_cost)); st.success(f"تمت الإضافة (ID: {tid})")
    st.markdown("---")
    treatments = get_treatments()
    st.dataframe(pd.DataFrame(treatments) if treatments else pd.DataFrame(columns=["id","name","base_cost"]), use_container_width=True)
    st.markdown("إعداد نسب التوزيع")
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
                if not (t_choice and d_choice and t_choice[1] and d_choice[1]): st.error("اختر علاجًا وطبيبًا")
                else:
                    set_treatment_percentage(t_choice[1], d_choice[1], float(clinic_perc), float(doctor_perc)); st.success("تم الحفظ")
    else:
        st.info("أضف طبيبًا وعلاجًا لتعيين النسب")
    st.markdown("قائمة نسب التوزيع"); tps = get_treatment_percentages(); st.dataframe(pd.DataFrame(tps) if tps else pd.DataFrame(), use_container_width=True)

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
            date = datetime_input("تاريخ ووقت الموعد", default=datetime.datetime.now() + datetime.timedelta(days=1))
            notes = st.text_area("ملاحظات")
            if st.form_submit_button("حجز"):
                if not (p_choice and d_choice and t_choice and p_choice[1] and d_choice[1] and t_choice[1]): st.error("اختر مريضًا وطبيبًا وعلاجًا")
                else:
                    aid = add_appointment(patient_id=p_choice[1], doctor_id=d_choice[1], treatment_id=t_choice[1], date=date, status="مجدول", notes=notes); st.success(f"تم حجز الموعد (ID: {aid})")
    st.markdown("---")
    appts = get_appointments()
    st.dataframe(pd.DataFrame(appts) if appts else pd.DataFrame(columns=["id","patient_name","doctor_name","treatment_name","date","status"]), use_container_width=True)

def payments_page_ui():
    st.header("الدفعات والفواتير")
    appts = get_appointments(); payments = get_payments()
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
                pid = add_payment(appointment_id=appt_id, total_amount=float(total_amount), paid_amount=float(paid_amount), payment_method=payment_method, discounts=float(discounts), taxes=float(taxes)); st.success(f"تم تسجيل الدفعة (ID: {pid})")
    st.markdown("---")
    st.dataframe(pd.DataFrame(payments) if payments else pd.DataFrame(columns=["id","date_paid","total_amount","paid_amount"]), use_container_width=True)
    st.markdown("طباعة فاتورة"); ids = [r["id"] for r in payments]; sel = st.selectbox("اختر دفعة للطباعة", options=[""] + ids)
    if sel:
        buf = generate_invoice_pdf_buffer(payment_id=int(sel)); st.download_button("تحميل PDF الفاتورة", data=buf, file_name=f"invoice_{sel}.pdf", mime="application/pdf")

def expenses_page_ui():
    st.header("المصروفات")
    with st.expander("إضافة مصروف", expanded=False):
        with st.form("add_exp"):
            desc = st.text_input("البيان"); category = st.text_input("التصنيف"); amount = st.number_input("المبلغ", min_value=0.0, value=0.0); date = st.date_input("التاريخ", value=datetime.date.today())
            if st.form_submit_button("حفظ"):
                add_expense(description=desc or None, category=category or None, amount=float(amount), date=datetime.datetime.combine(date, datetime.datetime.min.time())); st.success("تم الحفظ")
    st.markdown("---")
    exps = get_expenses(); st.dataframe(pd.DataFrame(exps) if exps else pd.DataFrame(columns=["id","description","category","amount","date"]), use_container_width=True)

def inventory_page_ui():
    st.header("إدارة المخزون")
    with st.expander("إضافة بند مخزون", expanded=False):
        with st.form("add_item"):
            name = st.text_input("اسم الصنف"); quantity = st.number_input("الكمية", min_value=0.0, value=0.0); unit = st.text_input("الوحدة"); cost = st.number_input("تكلفة الوحدة", min_value=0.0, value=0.0); low = st.number_input("حد التنبيه", min_value=0.0, value=5.0)
            if st.form_submit_button("إضافة"):
                if not name.strip(): st.error("أدخل اسم الصنف")
                else:
                    iid = add_inventory_item(name=name.strip(), quantity=float(quantity), unit=unit or None, cost_per_unit=float(cost), low_threshold=float(low)); st.success(f"تمت الإضافة (ID: {iid})")
    st.markdown("---")
    items = get_inventory_items(); st.dataframe(pd.DataFrame(items) if items else pd.DataFrame(columns=["id","name","quantity","unit","cost_per_unit","low_threshold"]), use_container_width=True)

def daily_entry_ui():
    st.header("الإدخال اليومي (حالات منجزة وحساب تلقائي للنسب)")
    sessions_t = get_treatments(); sessions_d = get_doctors()
    # We'll allow multiple rows of entries dynamically via number_input
    rows_count = st.number_input("كم حالة تريد إدخالها الآن؟", min_value=1, max_value=20, value=3, step=1)
    with st.form("daily_entry_form"):
        date = st.date_input("تاريخ الحالات", value=datetime.date.today())
        entries = []
        cols = []
        for i in range(int(rows_count)):
            c1, c2, c3, c4 = st.columns([3,3,2,4])
            with c1:
                t_choice = st.selectbox(f"العلاج #{i+1}", options=[""] + [f"{t['id']} - {t['name']}" for t in sessions_t], key=f"t_{i}")
            with c2:
                d_choice = st.selectbox(f"الطبيب #{i+1}", options=[""] + [f"{d['id']} - {d['name']}" for d in sessions_d], key=f"d_{i}")
            with c3:
                cost = st.number_input(f"تكلفة #{i+1}", min_value=0.0, key=f"cost_{i}")
            with c4:
                note = st.text_input(f"ملاحظات #{i+1}", key=f"note_{i}")
            entries.append((t_choice, d_choice, cost, note))
        st.markdown("---")
        st.write("المصروفات الإضافية اليوم (غير المرتبطة بمورد محدد)")
        extra_expenses = st.number_input("مصروفات إضافية اليوم", min_value=0.0, value=0.0)
        notes = st.text_area("ملاحظات عامة لملخّص اليوم")
        if st.form_submit_button("حفظ الإدخال اليومي"):
            # compute totals
            total_income = 0.0
            clinic_income = 0.0
            doctor_income = 0.0
            # For each entry, compute shares using TreatmentPercentage if exists
            with session_scope() as s:
                for t_choice, d_choice, cost, note in entries:
                    if not t_choice or not d_choice or (cost is None) or cost <= 0:
                        continue
                    try:
                        t_id = int(t_choice.split(" - ")[0])
                        d_id = int(d_choice.split(" - ")[0])
                    except Exception:
                        continue
                    # find perc
                    perc = s.query(TreatmentPercentage).filter_by(treatment_id=t_id, doctor_id=d_id).first()
                    if perc:
                        clinic_share = (perc.clinic_percentage or 50.0) * cost / 100.0
                        doctor_share = (perc.doctor_percentage or 50.0) * cost / 100.0
                    else:
                        clinic_share = cost * 0.5
                        doctor_share = cost * 0.5
                    total_income += cost
                    clinic_income += clinic_share
                    doctor_income += doctor_share
                # also include daily transactions incomes (if any added manually) - we treat extra income as not doctor-related
                # total expenses = extra_expenses + any Expense records entered for the day
                # Save summary
                net_profit = clinic_income - float(extra_expenses or 0.0)
                # Save to DB
                ds = DailySummary(date=datetime.datetime.combine(date, datetime.datetime.min.time()), total_income=total_income, clinic_income=clinic_income, doctor_income=doctor_income, total_expenses=float(extra_expenses or 0.0), net_profit=net_profit, notes=notes)
                s.add(ds)
                s.flush()
            st.success(f"تم حفظ ملخّص اليوم. إجمالي الدخل: {total_income:.2f} {CURRENCY_SYMBOL} — دخل العيادة: {clinic_income:.2f} {CURRENCY_SYMBOL} — دخل الأطباء: {doctor_income:.2f} {CURRENCY_SYMBOL} — الصافي بعد المصروفات: {net_profit:.2f} {CURRENCY_SYMBOL}")

def daily_summary_ui():
    st.header("الملخّصات اليومية")
    rows = get_daily_summaries()
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["id","date","total_income","clinic_income","doctor_income","total_expenses","net_profit","notes"])
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        fig = px.bar(df, x="date", y=["clinic_income","doctor_income","net_profit"], title="ملخّصات يومية")
        st.plotly_chart(fig, use_container_width=True)
    # export
    if st.button("تحميل ملخّصات كـ Excel"):
        bytes_x = df_to_excel_bytes(df)
        st.download_button("تحميل Excel", data=bytes_x, file_name="daily_summaries.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

from sqlalchemy.orm import joinedload

def financial_reports_page():
    st.title("📊 التقارير المالية المتقدمة")

    session = Session()
    payments = session.query(Payment).options(
        joinedload(Payment.appointment)
        .joinedload(Appointment.patient),
        joinedload(Payment.appointment)
        .joinedload(Appointment.doctor),
        joinedload(Payment.appointment)
        .joinedload(Appointment.treatment)
    ).all()

    expenses = session.query(Expense).all()
    session.close()


    if not payments and not expenses:
        st.info("لا توجد بيانات مالية بعد.")
        return

    st.subheader("تحديد الفترة الزمنية للتقرير")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("تاريخ البداية", datetime.date.today().replace(day=1))
    with col2:
        end_date = st.date_input("تاريخ النهاية", datetime.date.today())

    # ---- بيانات المدفوعات ----
    df_pay = pd.DataFrame([{
        "رقم العملية": p.id,
        "اسم المريض": p.appointment.patient.name if p.appointment and p.appointment.patient else "غير محدد",
        "الطبيب": p.appointment.doctor.name if p.appointment and p.appointment.doctor else "غير محدد",
        "العلاج": p.appointment.treatment.name if p.appointment and p.appointment.treatment else "غير محدد",
        "المبلغ الكلي": p.total_amount,
        "المدفوع": p.paid_amount,
        "نسبة العيادة": p.clinic_share,
        "نسبة الطبيب": p.doctor_share,
        "الخصومات": p.discounts,
        "الضرائب": p.taxes,
        "التاريخ": p.date_paid
    } for p in payments])

    if not df_pay.empty:
        # تحويل عمود التاريخ إلى نوع تاريخي
        df_pay["التاريخ"] = pd.to_datetime(df_pay["التاريخ"]).dt.date

        # فلترة حسب المدة المحددة
        df_pay = df_pay[(df_pay["التاريخ"] >= start_date) & (df_pay["التاريخ"] <= end_date)]

    # ---- بيانات المصروفات ----
    df_exp = pd.DataFrame([{
        "الوصف": e.description,
        "المبلغ": e.amount,
        "التاريخ": e.date
    } for e in expenses])

    if not df_exp.empty:
        df_exp["التاريخ"] = pd.to_datetime(df_exp["التاريخ"]).dt.date
        df_exp = df_exp[(df_exp["التاريخ"] >= start_date) & (df_exp["التاريخ"] <= end_date)]

    # ---- حساب الإجماليات ----
    total_income = df_pay["المدفوع"].sum() if not df_pay.empty else 0
    total_expenses = df_exp["المبلغ"].sum() if not df_exp.empty else 0
    clinic_net = total_income - total_expenses

    st.subheader("الملخص المالي")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("إجمالي الدخل", f"{total_income:,.2f} جنيه")
    with c2:
        st.metric("إجمالي المصروفات", f"{total_expenses:,.2f} جنيه")
    with c3:
        st.metric("صافي العيادة", f"{clinic_net:,.2f} جنيه")

    # ---- عرض التفاصيل ----
    with st.expander("عرض تفاصيل الإيرادات"):
        st.dataframe(df_pay, use_container_width=True)

    with st.expander("عرض تفاصيل المصروفات"):
        st.dataframe(df_exp, use_container_width=True)

    # ---- رسم بياني ----
    if not df_pay.empty or not df_exp.empty:
        combined_data = []
        if not df_pay.empty:
            for _, r in df_pay.iterrows():
                combined_data.append({"التاريخ": r["التاريخ"], "النوع": "إيراد", "القيمة": r["المدفوع"]})
        if not df_exp.empty:
            for _, r in df_exp.iterrows():
                combined_data.append({"التاريخ": r["التاريخ"], "النوع": "مصروف", "القيمة": -r["المبلغ"]})
        df_chart = pd.DataFrame(combined_data)
        df_chart = df_chart.groupby(["التاريخ", "النوع"]).sum().reset_index()
        st.subheader("التحليل الزمني")
        fig = px.line(df_chart, x="التاريخ", y="القيمة", color="النوع", markers=True)
        st.plotly_chart(fig, use_container_width=True)

def suppliers_page_ui():
    st.header("الموردين والمعامل")
    with st.expander("إضافة مورد / معمل جديد", expanded=False):
        with st.form("add_supplier"):
            name = st.text_input("الاسم"); category = st.selectbox("النوع", ["خامات", "معمل", "خدمات"])
            phone = st.text_input("الهاتف"); address = st.text_input("العنوان"); notes = st.text_area("ملاحظات")
            if st.form_submit_button("إضافة"):
                if not name.strip(): st.error("الاسم مطلوب")
                else:
                    sid = add_supplier(name=name.strip(), category=category or None, phone=phone or None, address=address or None, notes=notes or None)
                    st.success(f"تمت الإضافة (ID: {sid})")
    st.markdown("---")
    suppliers = get_suppliers()
    df = pd.DataFrame(suppliers) if suppliers else pd.DataFrame(columns=["id","name","category","phone","address","balance"])
    st.dataframe(df, use_container_width=True)

def supplier_details_ui():
    st.header("تفاصيل مورد / معمل")
    suppliers = get_suppliers()
    if not suppliers:
        st.info("لا توجد موردين بعد")
        return
    options = [f"{s['id']} - {s['name']}" for s in suppliers]
    sel = st.selectbox("اختر موردًا", options)
    if sel:
        sid = int(sel.split(" - ")[0])
        sup = next((x for x in suppliers if x["id"] == sid), None)
        if sup:
            st.subheader(f"{sup['name']}")
            st.write(f"النوع: {sup['category'] or '-'} — الهاتف: {sup['phone'] or '-'}")
            st.write(f"الرصيد الحالي: {format_money(sup['balance'] or 0.0)}")
            st.write(f"ملاحظات: {sup['notes'] or '-'}")
            st.markdown("---")
            st.subheader("إضافة حركة مالية للمورد")
            with st.form("add_sup_tr"):
                desc = st.text_input("البيان")
                amount = st.number_input("المبلغ (قيمة موجبة تزيد الرصيد)", value=0.0)
                method = st.selectbox("طريقة الدفع", ["نقدي", "تحويل بنكي", "شيك", "أخرى"])
                if st.form_submit_button("حفظ الحركة"):
                    add_supplier_transaction(supplier_id=sid, description=desc or None, amount=float(amount), payment_method=method or None)
                    st.success("تم حفظ الحركة")
            st.markdown("---")
            st.subheader("إضافة فاتورة مورد")
            with st.form("add_sup_inv"):
                inv_no = st.text_input("رقم الفاتورة")
                inv_amount = st.number_input("المبلغ", min_value=0.0, value=0.0)
                inv_desc = st.text_area("وصف الفاتورة")
                inv_date = st.date_input("تاريخ الفاتورة", value=datetime.date.today())
                paid_flag = st.checkbox("مدفوعة الآن")
                if st.form_submit_button("حفظ الفاتورة"):
                    add_supplier_invoice(supplier_id=sid, invoice_no=inv_no or f"INV-{uuid.uuid4().hex[:6]}", amount=float(inv_amount), description=inv_desc or None, date=datetime.datetime.combine(inv_date, datetime.datetime.min.time()), paid=bool(paid_flag))
                    st.success("تم إضافة الفاتورة")
            st.markdown("---")
            st.subheader("سجل الحركات")
            trs = get_supplier_transactions(sid); df_trs = pd.DataFrame(trs) if trs else pd.DataFrame(columns=["id","date","description","amount","payment_method"])
            st.dataframe(df_trs, use_container_width=True)
            st.subheader("فواتير المورد")
            invs = get_supplier_invoices(sid); df_invs = pd.DataFrame(invs) if invs else pd.DataFrame(columns=["id","invoice_no","date","amount","paid","description"])
            st.dataframe(df_invs, use_container_width=True)

def suppliers_report_ui():
    st.header("تقارير الموردين والمعامل")
    suppliers = get_suppliers()
    data = []
    for s in suppliers:
        trans = get_supplier_transactions(s["id"])
        total_transactions = sum(t["amount"] for t in trans) if trans else 0.0
        data.append({"الاسم": s["name"], "النوع": s["category"], "إجمالي التعاملات": total_transactions, "الرصيد الحالي": s["balance"] or 0.0})
    df = pd.DataFrame(data) if data else pd.DataFrame()
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        fig = px.bar(df, x="الاسم", y="الرصيد الحالي", color="النوع", title="الرصيد الحالي لكل مورد / معمل")
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------
# Backup utility
# ---------------------------
def download_db_button():
    db_path = DB_URI.replace("sqlite:///", "")
    if os.path.exists(db_path):
        with open(db_path, "rb") as f:
            st.download_button("تحميل نسخة احتياطية من قاعدة البيانات (.db)", f, file_name=os.path.basename(db_path))

# ---------------------------
# Main
# ---------------------------
def main():
    st.set_page_config(page_title="عيادة الأسنان - متكامل", layout="wide", page_icon="🦷")
    local_css_white(); app_header_white()

    menu = st.sidebar.selectbox("القسم", ["لوحة التحكم","المرضى","الأطباء","العلاجات","المواعيد","الدفعات","المصروفات","المخزون","الإدخال اليومي","الملخص اليومي","التقارير المالية","الموردين","تفاصيل مورد","تقارير الموردين","نسخة احتياطية"])
    if menu == "لوحة التحكم": dashboard_page()
    elif menu == "المرضى": patients_page_ui()
    elif menu == "الأطباء": doctors_page_ui()
    elif menu == "العلاجات": treatments_page_ui()
    elif menu == "المواعيد": appointments_page_ui()
    elif menu == "الدفعات": payments_page_ui()
    elif menu == "المصروفات": expenses_page_ui()
    elif menu == "المخزون": inventory_page_ui()
    elif menu == "الإدخال اليومي": daily_entry_ui()
    elif menu == "الملخص اليومي": daily_summary_ui()
    elif menu == "التقارير المالية": financial_reports_page()
    elif menu == "الموردين": suppliers_page_ui()
    elif menu == "تفاصيل مورد": supplier_details_ui()
    elif menu == "تقارير الموردين": suppliers_report_ui()
    elif menu == "نسخة احتياطية": download_db_button()
    else: st.write("اختر صفحة من القائمة")

if __name__ == "__main__":
    main()
