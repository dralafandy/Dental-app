# dental_clinic_app.py
import streamlit as st
import pandas as pd
import datetime
import os
import io
import uuid

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from contextlib import contextmanager

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import plotly.express as px

# Optional JS width helper
try:
    import streamlit_javascript as st_js
    HAS_ST_JS = True
except Exception:
    HAS_ST_JS = False

# -----------------------------
# Database setup
# -----------------------------
DB_URI = "sqlite:///dental_clinic.db"
engine = create_engine(DB_URI, echo=False, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()

# -----------------------------
# Models
# -----------------------------
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
    base_cost = Column(Float)

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
    amount = Column(Float)
    date = Column(DateTime)

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    quantity = Column(Float)
    unit = Column(String)
    cost_per_unit = Column(Float)

Base.metadata.create_all(engine)

# -----------------------------
# Helpers
# -----------------------------
def get_screen_width():
    if HAS_ST_JS:
        try:
            w = st_js.st_javascript("window.innerWidth")
            return int(w) if w else 1000
        except Exception:
            return 1000
    return 1000

def determine_num_columns(width):
    if width < 600:
        return 1
    elif width < 1000:
        return 2
    else:
        return 3

def secure_filename(ext=".png"):
    return f"{uuid.uuid4().hex}{ext}"

def save_uploaded_image(uploaded_file, prefix="img"):
    if uploaded_file is None:
        return None
    os.makedirs("images", exist_ok=True)
    _, ext = os.path.splitext(getattr(uploaded_file, "name", "upload.png"))
    filename = f"{prefix}_{secure_filename(ext)}"
    path = os.path.join("images", filename)
    with open(path, "wb") as f:
        f.write(uploaded_file.getvalue())
    return path

def datetime_input(label, value=None):
    """Return a datetime combining date_input and time_input (works even if streamlit datetime_input not available)."""
    if value is None:
        value = datetime.datetime.now()
    date_part = st.date_input(f"{label} التاريخ", value=value.date())
    time_part = st.time_input(f"{label} الوقت", value=value.time())
    return datetime.datetime.combine(date_part, time_part)

# -----------------------------
# DB session context manager
# -----------------------------
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

# -----------------------------
# CRUD: Add / Edit / Delete
# -----------------------------
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

# Doctors
def add_doctor(name, specialty=None, phone=None, email=None):
    with session_scope() as s:
        d = Doctor(name=name, specialty=specialty, phone=phone, email=email)
        s.add(d)
        s.flush()
        return d.id

def edit_doctor(doctor_id, name, specialty, phone, email):
    with session_scope() as s:
        d = s.get(Doctor, doctor_id)
        if not d:
            return False
        d.name = name
        d.specialty = specialty
        d.phone = phone
        d.email = email
        return True

def delete_doctor(doctor_id):
    with session_scope() as s:
        d = s.get(Doctor, doctor_id)
        if not d:
            return False
        s.delete(d)
        return True

# Treatments
def add_treatment(name, base_cost=0.0):
    with session_scope() as s:
        t = Treatment(name=name, base_cost=base_cost)
        s.add(t)
        s.flush()
        return t.id

def edit_treatment(treatment_id, name, base_cost):
    with session_scope() as s:
        t = s.get(Treatment, treatment_id)
        if not t:
            return False
        t.name = name
        t.base_cost = base_cost
        return True

def delete_treatment(treatment_id):
    with session_scope() as s:
        t = s.get(Treatment, treatment_id)
        if not t:
            return False
        s.delete(t)
        return True

# Treatment percentages
def set_treatment_percentage(treatment_id, doctor_id, clinic_percentage, doctor_percentage):
    with session_scope() as s:
        tp = s.query(TreatmentPercentage).filter_by(treatment_id=treatment_id, doctor_id=doctor_id).first()
        if not tp:
            tp = TreatmentPercentage(treatment_id=treatment_id, doctor_id=doctor_id,
                                     clinic_percentage=clinic_percentage, doctor_percentage=doctor_percentage)
            s.add(tp)
        else:
            tp.clinic_percentage = clinic_percentage
            tp.doctor_percentage = doctor_percentage
        s.flush()
        return True

def delete_treatment_percentage(tp_id):
    with session_scope() as s:
        tp = s.get(TreatmentPercentage, tp_id)
        if not tp:
            return False
        s.delete(tp)
        return True

# Appointments
def add_appointment(patient_id, doctor_id, treatment_id, date, status="مجدول", notes=None):
    with session_scope() as s:
        a = Appointment(patient_id=patient_id, doctor_id=doctor_id, treatment_id=treatment_id, date=date, status=status, notes=notes)
        s.add(a)
        s.flush()
        return a.id

def edit_appointment(appointment_id, patient_id, doctor_id, treatment_id, date, status, notes):
    with session_scope() as s:
        a = s.get(Appointment, appointment_id)
        if not a:
            return False
        a.patient_id = patient_id
        a.doctor_id = doctor_id
        a.treatment_id = treatment_id
        a.date = date
        a.status = status
        a.notes = notes
        return True

def delete_appointment(appointment_id):
    with session_scope() as s:
        a = s.get(Appointment, appointment_id)
        if not a:
            return False
        s.delete(a)
        return True

# Payments
def calculate_shares(appointment_id, total_amount, discounts=0.0, taxes=0.0):
    with session_scope() as s:
        appointment = s.get(Appointment, appointment_id) if appointment_id else None
        if appointment:
            perc = s.query(TreatmentPercentage).filter_by(treatment_id=appointment.treatment_id, doctor_id=appointment.doctor_id).first()
            if perc:
                clinic_perc = perc.clinic_percentage or 50.0
                doctor_perc = perc.doctor_percentage or 50.0
            else:
                clinic_perc = doctor_perc = 50.0
        else:
            clinic_perc = doctor_perc = 50.0
    net = float(total_amount) - float(discounts or 0.0) + float(taxes or 0.0)
    clinic_share = round(net * (clinic_perc / 100.0), 2)
    doctor_share = round(net * (doctor_perc / 100.0), 2)
    return clinic_share, doctor_share

def add_payment(appointment_id, total_amount, paid_amount, payment_method, discounts=0.0, taxes=0.0):
    clinic_share, doctor_share = calculate_shares(appointment_id, total_amount, discounts, taxes)
    with session_scope() as s:
        p = Payment(appointment_id=appointment_id, total_amount=total_amount, paid_amount=paid_amount,
                    clinic_share=clinic_share, doctor_share=doctor_share,
                    payment_method=payment_method, discounts=discounts, taxes=taxes, date_paid=datetime.datetime.now())
        s.add(p)
        s.flush()
        return p.id

def delete_payment(payment_id):
    with session_scope() as s:
        p = s.get(Payment, payment_id)
        if not p:
            return False
        s.delete(p)
        return True

# Expenses
def add_expense(description, amount, date=None):
    if date is None:
        date = datetime.datetime.now()
    with session_scope() as s:
        e = Expense(description=description, amount=amount, date=date)
        s.add(e)
        s.flush()
        return e.id

def delete_expense(expense_id):
    with session_scope() as s:
        e = s.get(Expense, expense_id)
        if not e:
            return False
        s.delete(e)
        return True

# Inventory
def add_inventory_item(name, quantity, unit, cost_per_unit):
    with session_scope() as s:
        it = InventoryItem(name=name, quantity=quantity, unit=unit, cost_per_unit=cost_per_unit)
        s.add(it)
        s.flush()
        return it.id

def edit_inventory_item(item_id, name, quantity, unit, cost_per_unit):
    with session_scope() as s:
        it = s.get(InventoryItem, item_id)
        if not it:
            return False
        it.name = name
        it.quantity = quantity
        it.unit = unit
        it.cost_per_unit = cost_per_unit
        return True

def delete_inventory_item(item_id):
    with session_scope() as s:
        it = s.get(InventoryItem, item_id)
        if not it:
            return False
        s.delete(it)
        return True

# -----------------------------
# Safe GET functions (return dicts)
# -----------------------------
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

def get_doctors():
    with session_scope() as s:
        rows = s.query(Doctor).order_by(Doctor.id).all()
        data = [{"id": r.id, "name": r.name, "specialty": r.specialty, "phone": r.phone, "email": r.email} for r in rows]
        return data

def get_treatments():
    with session_scope() as s:
        rows = s.query(Treatment).order_by(Treatment.id).all()
        data = [{"id": r.id, "name": r.name, "base_cost": r.base_cost} for r in rows]
        return data

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

def get_expenses():
    with session_scope() as s:
        rows = s.query(Expense).order_by(Expense.date.desc()).all()
        data = [{"id": r.id, "description": r.description, "amount": r.amount, "date": r.date} for r in rows]
        return data

def get_inventory_items():
    with session_scope() as s:
        rows = s.query(InventoryItem).order_by(InventoryItem.id).all()
        data = [{"id": r.id, "name": r.name, "quantity": r.quantity, "unit": r.unit, "cost_per_unit": r.cost_per_unit} for r in rows]
        return data

# -----------------------------
# PDF invoice generation
# -----------------------------
def generate_invoice_pdf(payment_id=None, appointment_id=None):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "فاتورة - عيادة الأسنان")
    y -= 30
    if payment_id:
        with session_scope() as s:
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
        with session_scope() as s:
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

# -----------------------------
# Streamlit pages
# -----------------------------
def patients_page(num_cols):
    st.header("إدارة المرضى")
    with st.expander("إضافة مريض جديد", expanded=False):
        with st.form("add_patient"):
            cols = st.columns(num_cols)
            # defaults to avoid UnboundLocal
            name = ""
            age = 0
            gender = ""
            phone = ""
            address = ""
            medical_history = ""
            image = None

            with cols[0]:
                name = st.text_input("الاسم", value=name)
                age = st.number_input("العمر", min_value=0, value=age, step=1)
            if num_cols > 1:
                with cols[1]:
                    gender = st.selectbox("الجنس", ["", "ذكر", "أنثى"], index=0)
                    phone = st.text_input("الهاتف", value=phone)
            if num_cols > 2:
                with cols[2]:
                    address = st.text_input("العنوان", value=address)

            medical_history = st.text_area("التاريخ الطبي", value=medical_history)
            image = st.file_uploader("رفع صورة (اختياري)", type=["png", "jpg", "jpeg"])
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("الاسم مطلوب")
                else:
                    pid = add_patient(name=name.strip(), age=int(age), gender=gender or None,
                                      phone=phone or None, address=address or None,
                                      medical_history=medical_history or None, image=image)
                    st.success(f"تمت إضافة المريض (ID: {pid})")

    st.markdown("---")
    patients = get_patients()
    df = pd.DataFrame(patients) if patients else pd.DataFrame(columns=["id", "name", "age", "gender", "phone", "address"])
    search = st.text_input("بحث (الاسم/الهاتف/العنوان)")
    if search:
        mask = df.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
        df = df[mask]
    st.dataframe(df, use_container_width=True)

    st.markdown("### تحرير / حذف مريض")
    ids = [r["id"] for r in patients]
    sel = st.selectbox("اختر ID للمريض", options=[""] + ids)
    if sel:
        pid = int(sel)
        # fetch single patient raw dict
        p = next((x for x in patients if x["id"] == pid), None)
        if p:
            with st.form("edit_patient"):
                name = st.text_input("الاسم", value=p["name"])
                age = st.number_input("العمر", min_value=0, value=p["age"] or 0, step=1)
                gender = st.selectbox("الجنس", ["", "ذكر", "أنثى"], index=(0 if not p["gender"] else (1 if p["gender"]=="ذكر" else 2)))
                phone = st.text_input("الهاتف", value=p["phone"] or "")
                address = st.text_input("العنوان", value=p["address"] or "")
                medical_history = st.text_area("التاريخ الطبي", value=p["medical_history"] or "")
                image = st.file_uploader("رفع صورة جديدة (اختياري)", type=["png", "jpg", "jpeg"])
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("حفظ"):
                        ok = edit_patient(pid, name=name.strip(), age=int(age), gender=gender or None,
                                          phone=phone or None, address=address or None,
                                          medical_history=medical_history or None, image=image)
                        if ok:
                            st.success("تم الحفظ")
                        else:
                            st.error("حدث خطأ")
                with c2:
                    if st.button("حذف"):
                        ok = delete_patient(pid)
                        if ok:
                            st.success("تم الحذف")
                        else:
                            st.error("فشل الحذف")

def doctors_page(num_cols):
    st.header("إدارة الأطباء")
    with st.expander("إضافة طبيب جديد", expanded=False):
        with st.form("add_doctor"):
            cols = st.columns(num_cols)
            name = ""
            specialty = ""
            phone = ""
            email = ""
            with cols[0]:
                name = st.text_input("الاسم", value=name)
                specialty = st.text_input("التخصص", value=specialty)
            if num_cols > 1:
                with cols[1]:
                    phone = st.text_input("الهاتف", value=phone)
                    email = st.text_input("البريد الإلكتروني", value=email)
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("الاسم مطلوب")
                else:
                    did = add_doctor(name=name.strip(), specialty=specialty or None, phone=phone or None, email=email or None)
                    st.success(f"تمت إضافة الطبيب (ID: {did})")
    st.markdown("---")
    doctors = get_doctors()
    df = pd.DataFrame(doctors) if doctors else pd.DataFrame(columns=["id","name","specialty","phone","email"])
    search = st.text_input("بحث في الأطباء")
    if search:
        mask = df.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
        df = df[mask]
    st.dataframe(df, use_container_width=True)

    st.markdown("### تحرير / حذف طبيب")
    ids = [r["id"] for r in doctors]
    sel = st.selectbox("اختر ID للطبيب", options=[""] + ids)
    if sel:
        did = int(sel)
        d = next((x for x in doctors if x["id"] == did), None)
        if d:
            with st.form("edit_doctor"):
                name = st.text_input("الاسم", value=d["name"])
                specialty = st.text_input("التخصص", value=d["specialty"] or "")
                phone = st.text_input("الهاتف", value=d["phone"] or "")
                email = st.text_input("البريد الإلكتروني", value=d["email"] or "")
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("حفظ"):
                        ok = edit_doctor(did, name=name.strip(), specialty=specialty or None, phone=phone or None, email=email or None)
                        if ok:
                            st.success("تم الحفظ")
                        else:
                            st.error("فشل الحفظ")
                with c2:
                    if st.button("حذف"):
                        ok = delete_doctor(did)
                        if ok:
                            st.success("تم الحذف")
                        else:
                            st.error("فشل الحذف")

def treatments_page(num_cols):
    st.header("إدارة العلاجات")
    with st.expander("إضافة علاج جديد", expanded=False):
        with st.form("add_treatment"):
            name = st.text_input("اسم العلاج")
            base_cost = st.number_input("السعر الأساسي", min_value=0.0, value=0.0)
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("الاسم مطلوب")
                else:
                    tid = add_treatment(name=name.strip(), base_cost=float(base_cost))
                    st.success(f"تمت إضافة العلاج (ID: {tid})")
    st.markdown("---")
    treatments = get_treatments()
    df = pd.DataFrame(treatments) if treatments else pd.DataFrame(columns=["id","name","base_cost"])
    st.dataframe(df, use_container_width=True)

    st.markdown("### إعداد نسب التوزيع")
    doctors = get_doctors()
    treatments = get_treatments()
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
    df2 = pd.DataFrame(tps) if tps else pd.DataFrame(columns=["id","treatment_name","doctor_name","clinic_percentage","doctor_percentage"])
    st.dataframe(df2, use_container_width=True)

def appointments_page(num_cols):
    st.header("إدارة المواعيد")
    patients = get_patients()
    doctors = get_doctors()
    treatments = get_treatments()

    with st.expander("حجز موعد جديد", expanded=False):
        with st.form("add_appointment"):
            p_opts = [(f"{p['id']} - {p['name']}", p['id']) for p in patients]
            d_opts = [(f"{d['id']} - {d['name']}", d['id']) for d in doctors]
            t_opts = [(f"{t['id']} - {t['name']}", t['id']) for t in treatments]
            p_choice = st.selectbox("اختر مريض", options=[("",None)] + p_opts, format_func=lambda x: x[0] if x else "")
            d_choice = st.selectbox("اختر طبيب", options=[("",None)] + d_opts, format_func=lambda x: x[0] if x else "")
            t_choice = st.selectbox("اختر علاج", options=[("",None)] + t_opts, format_func=lambda x: x[0] if x else "")
            date = datetime_input("تاريخ ووقت الموعد", value=datetime.datetime.now() + datetime.timedelta(days=1))
            notes = st.text_area("ملاحظات")
            if st.form_submit_button("حجز"):
                if not (p_choice and d_choice and t_choice and p_choice[1] and d_choice[1] and t_choice[1]):
                    st.error("اختر مريضًا وطبيبًا وعلاجًا")
                else:
                    appt_id = add_appointment(patient_id=p_choice[1], doctor_id=d_choice[1], treatment_id=t_choice[1], date=date, status="مجدول", notes=notes)
                    st.success(f"تم حجز الموعد (ID: {appt_id})")
    st.markdown("---")
    appts = get_appointments()
    df = pd.DataFrame(appts) if appts else pd.DataFrame(columns=["id","patient_name","doctor_name","treatment_name","date","status"])
    search = st.text_input("بحث في المواعيد")
    if search:
        mask = df.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
        df = df[mask]
    st.dataframe(df, use_container_width=True)

    st.markdown("### تعديل / حذف موعد")
    ids = [r["id"] for r in appts]
    sel = st.selectbox("اختر ID للموعد", options=[""] + ids)
    if sel:
        aid = int(sel)
        a = next((x for x in appts if x["id"] == aid), None)
        if a:
            with st.form("edit_appoint"):
                p_opts = [(f"{p['id']} - {p['name']}", p['id']) for p in patients]
                d_opts = [(f"{d['id']} - {d['name']}", d['id']) for d in doctors]
                t_opts = [(f"{t['id']} - {t['name']}", t['id']) for t in treatments]
                # find index functions
                def find_idx(opts, val):
                    for i,o in enumerate(opts):
                        if o[1] == val:
                            return i
                    return 0
                p_idx = find_idx(p_opts, a["patient_id"])
                d_idx = find_idx(d_opts, a["doctor_id"])
                t_idx = find_idx(t_opts, a["treatment_id"])
                p_choice = st.selectbox("المريض", options=p_opts, index=p_idx, format_func=lambda x: x[0])
                d_choice = st.selectbox("الطبيب", options=d_opts, index=d_idx, format_func=lambda x: x[0])
                t_choice = st.selectbox("العلاج", options=t_opts, index=t_idx, format_func=lambda x: x[0])
                date = datetime_input("تاريخ ووقت الموعد", value=a["date"] or datetime.datetime.now())
                status = st.selectbox("الحالة", ["مجدول", "تم", "ملغي", "مؤجل"], index=["مجدول","تم","ملغي","مؤجل"].index(a["status"]) if a["status"] in ["مجدول","تم","ملغي","مؤجل"] else 0)
                notes = st.text_area("ملاحظات", value=a["notes"] or "")
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("حفظ"):
                        ok = edit_appointment(aid, patient_id=p_choice[1], doctor_id=d_choice[1], treatment_id=t_choice[1], date=date, status=status, notes=notes)
                        if ok:
                            st.success("تم الحفظ")
                        else:
                            st.error("فشل الحفظ")
                with c2:
                    if st.button("حذف"):
                        ok = delete_appointment(aid)
                        if ok:
                            st.success("تم الحذف")
                        else:
                            st.error("فشل الحذف")

def payments_page(num_cols):
    st.header("الدفعات والفواتير")
    appts = get_appointments()
    payments = get_payments()
    with st.expander("تسجيل دفعة جديدة", expanded=False):
        with st.form("add_payment"):
            appt_opts = [(f"{a['id']} - {a['patient_name']} - {a['date']}", a['id']) for a in appts]
            appt_choice = st.selectbox("اختر موعد (اختياري)", options=[("",None)] + appt_opts, format_func=lambda x: x[0] if x else "")
            total_amount = st.number_input("المبلغ الإجمالي", min_value=0.0, value=0.0)
            discounts = st.number_input("الخصم", min_value=0.0, value=0.0)
            taxes = st.number_input("الضرائب", min_value=0.0, value=0.0)
            paid_amount = st.number_input("المبلغ المدفوع", min_value=0.0, value=0.0)
            payment_method = st.selectbox("طريقة الدفع", ["نقدًا", "بطاقة", "تحويل بنكي", "أخرى"])
            if st.form_submit_button("تسجيل"):
                appt_id = appt_choice[1] if appt_choice else None
                pid = add_payment(appointment_id=appt_id, total_amount=float(total_amount), paid_amount=float(paid_amount), payment_method=payment_method, discounts=float(discounts), taxes=float(taxes))
                st.success(f"تم تسجيل الدفعة (ID: {pid})")
    st.markdown("---")
    df = pd.DataFrame(payments) if payments else pd.DataFrame(columns=["id","date_paid","total_amount","paid_amount"])
    st.dataframe(df, use_container_width=True)
    st.markdown("### طباعة فاتورة PDF")
    ids = [r["id"] for r in payments]
    sel = st.selectbox("اختر ID للفاتورة", options=[""] + ids)
    if sel:
        pid = int(sel)
        buf = generate_invoice_pdf(payment_id=pid)
        st.download_button("تحميل PDF", data=buf, file_name=f"invoice_{pid}.pdf", mime="application/pdf")
    st.markdown("### حذف دفعة")
    del_id = st.number_input("أدخل ID للحذف (اختياري)", min_value=0, value=0, step=1)
    if st.button("حذف الدفعة"):
        if del_id > 0:
            ok = delete_payment(int(del_id))
            if ok:
                st.success("تم الحذف")
            else:
                st.error("لم يتم العثور على الدفعة")

def expenses_page(num_cols):
    st.header("المصروفات")
    with st.expander("إضافة مصروف", expanded=False):
        with st.form("add_expense"):
            desc = st.text_input("البيان")
            amount = st.number_input("المبلغ", min_value=0.0, value=0.0)
            date = st.date_input("التاريخ", value=datetime.date.today())
            if st.form_submit_button("إضافة"):
                add_expense(description=desc or None, amount=float(amount), date=datetime.datetime.combine(date, datetime.datetime.min.time()))
                st.success("تمت الإضافة")
    st.markdown("---")
    expenses = get_expenses()
    df = pd.DataFrame(expenses) if expenses else pd.DataFrame(columns=["id","description","amount","date"])
    st.dataframe(df, use_container_width=True)
    st.markdown("### حذف مصروف")
    ids = [r["id"] for r in expenses]
    sel = st.selectbox("اختر ID للمصروف للحذف", options=[""] + ids)
    if sel:
        if st.button("حذف المصروف"):
            ok = delete_expense(int(sel))
            if ok:
                st.success("تم الحذف")
            else:
                st.error("فشل الحذف")

def inventory_page(num_cols):
    st.header("إدارة المخزون")
    with st.expander("إضافة بند مخزون", expanded=False):
        with st.form("add_inv"):
            name = st.text_input("اسم الصنف")
            quantity = st.number_input("الكمية", min_value=0.0, value=0.0)
            unit = st.text_input("الوحدة (مثال: قطعة)")
            cost_per_unit = st.number_input("تكلفة الوحدة", min_value=0.0, value=0.0)
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("أدخل اسم الصنف")
                else:
                    iid = add_inventory_item(name=name.strip(), quantity=float(quantity), unit=unit or None, cost_per_unit=float(cost_per_unit))
                    st.success(f"تمت الإضافة (ID: {iid})")
    st.markdown("---")
    items = get_inventory_items()
    df = pd.DataFrame(items) if items else pd.DataFrame(columns=["id","name","quantity","unit","cost_per_unit"])
    st.dataframe(df, use_container_width=True)
    st.markdown("### تعديل / حذف صنف")
    ids = [r["id"] for r in items]
    sel = st.selectbox("اختر ID للصنف", options=[""] + ids)
    if sel:
        iid = int(sel)
        it = next((x for x in items if x["id"] == iid), None)
        if it:
            with st.form("edit_inv"):
                name = st.text_input("الاسم", value=it["name"])
                quantity = st.number_input("الكمية", min_value=0.0, value=it["quantity"])
                unit = st.text_input("الوحدة", value=it["unit"] or "")
                cost_per_unit = st.number_input("تكلفة الوحدة", min_value=0.0, value=it["cost_per_unit"] or 0.0)
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("حفظ"):
                        ok = edit_inventory_item(iid, name=name.strip(), quantity=float(quantity), unit=unit or None, cost_per_unit=float(cost_per_unit))
                        if ok:
                            st.success("تم الحفظ")
                        else:
                            st.error("فشل الحفظ")
                with c2:
                    if st.button("حذف الصنف"):
                        ok = delete_inventory_item(iid)
                        if ok:
                            st.success("تم الحذف")
                        else:
                            st.error("فشل الحذف")

def reports_page(num_cols):
    st.header("التقارير المالية")
    payments = get_payments()
    expenses = get_expenses()
    df_pay = pd.DataFrame([{
        "date": p["date_paid"].date() if p["date_paid"] else None,
        "clinic_share": p["clinic_share"] or 0.0,
        "doctor_share": p["doctor_share"] or 0.0,
        "total": p["total_amount"] or 0.0
    } for p in payments]) if payments else pd.DataFrame()

    df_exp = pd.DataFrame([{
        "date": e["date"].date() if e["date"] else None,
        "amount": e["amount"] or 0.0
    } for e in expenses]) if expenses else pd.DataFrame()

    total_income = df_pay["total"].sum() if not df_pay.empty else 0.0
    total_clinic = df_pay["clinic_share"].sum() if not df_pay.empty else 0.0
    total_doctor = df_pay["doctor_share"].sum() if not df_pay.empty else 0.0
    total_expenses = df_exp["amount"].sum() if not df_exp.empty else 0.0
    net_profit = total_clinic - total_expenses

    st.metric("إجمالي الإيرادات", f"{total_income:.2f}")
    st.metric("إجمالي حصة العيادة", f"{total_clinic:.2f}")
    st.metric("إجمالي حصة الأطباء", f"{total_doctor:.2f}")
    st.metric("إجمالي المصروفات", f"{total_expenses:.2f}")
    st.metric("صافي الربح (حصة العيادة - المصروفات)", f"{net_profit:.2f}")

    st.markdown("---")
    st.subheader("الإيرادات عبر الزمن")
    if not df_pay.empty:
        agg = df_pay.groupby("date").sum().reset_index().sort_values("date")
        fig = px.line(agg, x="date", y=["clinic_share", "doctor_share"], labels={"value":"المبلغ","variable":"النوع"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد دفعات لعرضها")

    st.subheader("المصروفات عبر الزمن")
    if not df_exp.empty:
        agg2 = df_exp.groupby("date").sum().reset_index().sort_values("date")
        fig2 = px.bar(agg2, x="date", y="amount", labels={"amount":"المصروف"})
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("لا توجد مصروفات لعرضها")

    st.markdown("---")
    st.subheader("تصدير بيانات")
    if payments:
        df_all = pd.DataFrame(payments)
        buf = io.BytesIO()
        buf.write(df_all.to_csv(index=False).encode("utf-8"))
        buf.seek(0)
        st.download_button("تحميل ملخص الدفعات (CSV)", data=buf, file_name="payments_summary.csv", mime="text/csv")
    else:
        st.info("لا توجد دفعات للتصدير")

# -----------------------------
# Main
# -----------------------------
def main():
    st.set_page_config(page_title="عيادة الأسنان", layout="wide", page_icon="🦷")
    width = get_screen_width()
    num_cols = determine_num_columns(width)

    st.sidebar.title("القسم")
    page = st.sidebar.selectbox("اختر الصفحة", [
        "إدارة المرضى",
        "إدارة الأطباء",
        "إدارة العلاجات",
        "إدارة المواعيد",
        "الدفعات",
        "المصروفات",
        "إدارة المخزون",
        "التقارير"
    ])

    if page == "إدارة المرضى":
        patients_page(num_cols)
    elif page == "إدارة الأطباء":
        doctors_page(num_cols)
    elif page == "إدارة العلاجات":
        treatments_page(num_cols)
    elif page == "إدارة المواعيد":
        appointments_page(num_cols)
    elif page == "الدفعات":
        payments_page(num_cols)
    elif page == "المصروفات":
        expenses_page(num_cols)
    elif page == "إدارة المخزون":
        inventory_page(num_cols)
    elif page == "التقارير":
        reports_page(num_cols)
    else:
        st.write("اختر صفحة من القائمة")

if __name__ == "__main__":
    main()
