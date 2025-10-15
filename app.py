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

# Optional: try to use streamlit_javascript for screen width; if missing, fallback
try:
    import streamlit_javascript as st_js
    HAS_ST_JS = True
except Exception:
    HAS_ST_JS = False

# --- Database Setup ---
DB_PATH = "sqlite:///dental_clinic.db"
engine = create_engine(DB_PATH, echo=False, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()

# --- Models ---
class Patient(Base):
    __tablename__ = 'patients'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    gender = Column(String)
    phone = Column(String)
    address = Column(String)
    medical_history = Column(Text)
    image_path = Column(String)

class Doctor(Base):
    __tablename__ = 'doctors'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    specialty = Column(String)
    phone = Column(String)
    email = Column(String)

class Treatment(Base):
    __tablename__ = 'treatments'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    base_cost = Column(Float)

class TreatmentPercentage(Base):
    __tablename__ = 'treatment_percentages'
    id = Column(Integer, primary_key=True)
    treatment_id = Column(Integer, ForeignKey('treatments.id'))
    doctor_id = Column(Integer, ForeignKey('doctors.id'))
    clinic_percentage = Column(Float)
    doctor_percentage = Column(Float)
    treatment = relationship("Treatment")
    doctor = relationship("Doctor")

class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'))
    doctor_id = Column(Integer, ForeignKey('doctors.id'))
    treatment_id = Column(Integer, ForeignKey('treatments.id'))
    date = Column(DateTime)
    status = Column(String)
    notes = Column(Text)
    patient = relationship("Patient")
    doctor = relationship("Doctor")
    treatment = relationship("Treatment")

class Payment(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True)
    appointment_id = Column(Integer, ForeignKey('appointments.id'), nullable=True)
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
    __tablename__ = 'expenses'
    id = Column(Integer, primary_key=True)
    description = Column(String)
    amount = Column(Float)
    date = Column(DateTime)

class InventoryItem(Base):
    __tablename__ = 'inventory_items'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    quantity = Column(Float)
    unit = Column(String)
    cost_per_unit = Column(Float)

Base.metadata.create_all(engine)

# --- DB session context manager ---
@contextmanager
def get_session():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# --- Utility Functions ---
def get_screen_width():
    # Try streamlit_javascript, otherwise fallback to 1000
    if HAS_ST_JS:
        try:
            width = st_js.st_javascript("window.innerWidth")
            return int(width) if width else 1000
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

def secure_filename():
    return uuid.uuid4().hex

def save_uploaded_image(image_file, prefix="img"):
    """Save uploaded Streamlit file to images/ and return path (or None)."""
    if image_file is None:
        return None
    os.makedirs("images", exist_ok=True)
    # keep extension if possible
    ext = os.path.splitext(image_file.name)[1] if hasattr(image_file, "name") else ".png"
    filename = f"{prefix}_{secure_filename()}{ext}"
    path = os.path.join("images", filename)
    with open(path, "wb") as f:
        f.write(image_file.getvalue())
    return path

def datetime_input(label, value=None):
    """
    Cross-version safe datetime input: combine date_input + time_input.
    Returns a datetime.datetime object.
    """
    if value is None:
        value = datetime.datetime.now()
    date_val = st.date_input(f"{label} - التاريخ", value=value.date())
    time_val = st.time_input(f"{label} - الوقت", value=value.time())
    return datetime.datetime.combine(date_val, time_val)

# --- CRUD Functions ---
# Patients
def add_patient(name, age=None, gender=None, phone=None, address=None, medical_history=None, image=None):
    with get_session() as session:
        patient = Patient(
            name=name,
            age=age,
            gender=gender,
            phone=phone,
            address=address,
            medical_history=medical_history
        )
        if image:
            patient.image_path = save_uploaded_image(image, prefix="patient")
        session.add(patient)
        session.flush()
        return patient.id

def get_patients():
    session = Session()
    patients = session.query(Patient).all()
    data = []
    for p in patients:
        data.append({
            "id": p.id,
            "name": p.name,
            "age": p.age,
            "gender": p.gender,
            "phone": p.phone,
            "address": p.address,
            "medical_history": p.medical_history,
            "image_path": p.image_path
        })
    session.close()
    return data
def get_patient(patient_id):
    with get_session() as session:
        return session.get(Patient, patient_id)

def edit_patient(patient_id, name, age, gender, phone, address, medical_history, image=None):
    with get_session() as session:
        patient = session.get(Patient, patient_id)
        if not patient:
            return False
        patient.name = name
        patient.age = age
        patient.gender = gender
        patient.phone = phone
        patient.address = address
        patient.medical_history = medical_history
        if image:
            patient.image_path = save_uploaded_image(image, prefix="patient")
        return True

def delete_patient(patient_id):
    with get_session() as session:
        patient = session.get(Patient, patient_id)
        if patient:
            session.delete(patient)
            return True
    return False

# Doctors
def add_doctor(name, specialty=None, phone=None, email=None):
    with get_session() as session:
        doc = Doctor(name=name, specialty=specialty, phone=phone, email=email)
        session.add(doc)
        session.flush()
        return doc.id

def get_doctors():
    with get_session() as session:
        return session.query(Doctor).order_by(Doctor.id).all()

def get_doctor(doctor_id):
    with get_session() as session:
        return session.get(Doctor, doctor_id)

def edit_doctor(doctor_id, name, specialty, phone, email):
    with get_session() as session:
        doc = session.get(Doctor, doctor_id)
        if not doc:
            return False
        doc.name = name
        doc.specialty = specialty
        doc.phone = phone
        doc.email = email
        return True

def delete_doctor(doctor_id):
    with get_session() as session:
        doc = session.get(Doctor, doctor_id)
        if doc:
            session.delete(doc)
            return True
    return False

# Treatments
def add_treatment(name, base_cost):
    with get_session() as session:
        t = Treatment(name=name, base_cost=base_cost)
        session.add(t)
        session.flush()
        return t.id

def get_treatments():
    with get_session() as session:
        return session.query(Treatment).order_by(Treatment.id).all()

def get_treatment(treatment_id):
    with get_session() as session:
        return session.get(Treatment, treatment_id)

def edit_treatment(treatment_id, name, base_cost):
    with get_session() as session:
        t = session.get(Treatment, treatment_id)
        if not t:
            return False
        t.name = name
        t.base_cost = base_cost
        return True

def delete_treatment(treatment_id):
    with get_session() as session:
        t = session.get(Treatment, treatment_id)
        if t:
            session.delete(t)
            return True
    return False

# Treatment Percentage
def set_treatment_percentage(treatment_id, doctor_id, clinic_percentage, doctor_percentage):
    with get_session() as session:
        tp = session.query(TreatmentPercentage).filter_by(treatment_id=treatment_id, doctor_id=doctor_id).first()
        if not tp:
            tp = TreatmentPercentage(treatment_id=treatment_id, doctor_id=doctor_id,
                                     clinic_percentage=clinic_percentage, doctor_percentage=doctor_percentage)
            session.add(tp)
        else:
            tp.clinic_percentage = clinic_percentage
            tp.doctor_percentage = doctor_percentage
        return True

def get_treatment_percentages():
    with get_session() as session:
        return session.query(TreatmentPercentage).order_by(TreatmentPercentage.id).all()

# Appointments
def add_appointment(patient_id, doctor_id, treatment_id, date, status="مجدول", notes=None):
    with get_session() as session:
        appt = Appointment(patient_id=patient_id, doctor_id=doctor_id, treatment_id=treatment_id,
                           date=date, status=status, notes=notes)
        session.add(appt)
        session.flush()
        return appt.id

def get_appointments():
    with get_session() as session:
        return session.query(Appointment).order_by(Appointment.date.desc()).all()

def get_appointment(appointment_id):
    with get_session() as session:
        return session.get(Appointment, appointment_id)

def edit_appointment(appointment_id, patient_id, doctor_id, treatment_id, date, status, notes):
    with get_session() as session:
        appt = session.get(Appointment, appointment_id)
        if not appt:
            return False
        appt.patient_id = patient_id
        appt.doctor_id = doctor_id
        appt.treatment_id = treatment_id
        appt.date = date
        appt.status = status
        appt.notes = notes
        return True

def delete_appointment(appointment_id):
    with get_session() as session:
        appt = session.get(Appointment, appointment_id)
        if appt:
            session.delete(appt)
            return True
    return False

# Payment calculation and CRUD
def calculate_shares(appointment_id, total_amount, discounts=0.0, taxes=0.0):
    with get_session() as session:
        appointment = session.get(Appointment, appointment_id) if appointment_id else None
        if not appointment:
            clinic_perc = 50.0
            doctor_perc = 50.0
        else:
            perc = session.query(TreatmentPercentage).filter_by(
                treatment_id=appointment.treatment_id,
                doctor_id=appointment.doctor_id).first()
            if perc:
                clinic_perc = perc.clinic_percentage or 50.0
                doctor_perc = perc.doctor_percentage or 50.0
            else:
                clinic_perc = 50.0
                doctor_perc = 50.0
    net_amount = float(total_amount) - float(discounts or 0.0) + float(taxes or 0.0)
    clinic_share = round(net_amount * (clinic_perc / 100.0), 2)
    doctor_share = round(net_amount * (doctor_perc / 100.0), 2)
    return clinic_share, doctor_share

def add_payment(appointment_id, total_amount, paid_amount, payment_method, discounts=0.0, taxes=0.0):
    with get_session() as session:
        clinic_share, doctor_share = calculate_shares(appointment_id, total_amount, discounts, taxes)
        p = Payment(
            appointment_id=appointment_id,
            total_amount=total_amount,
            paid_amount=paid_amount,
            clinic_share=clinic_share,
            doctor_share=doctor_share,
            payment_method=payment_method,
            discounts=discounts,
            taxes=taxes,
            date_paid=datetime.datetime.now()
        )
        session.add(p)
        session.flush()
        return p.id

def get_payments():
    with get_session() as session:
        return session.query(Payment).order_by(Payment.date_paid.desc()).all()

# Expenses
def add_expense(description, amount, date=None):
    with get_session() as session:
        if date is None:
            date = datetime.datetime.now()
        e = Expense(description=description, amount=amount, date=date)
        session.add(e)
        session.flush()
        return e.id

def get_expenses():
    with get_session() as session:
        return session.query(Expense).order_by(Expense.date.desc()).all()

def delete_expense(expense_id):
    with get_session() as session:
        e = session.get(Expense, expense_id)
        if e:
            session.delete(e)
            return True
    return False

# Inventory
def add_inventory_item(name, quantity, unit, cost_per_unit):
    with get_session() as session:
        it = InventoryItem(name=name, quantity=quantity, unit=unit, cost_per_unit=cost_per_unit)
        session.add(it)
        session.flush()
        return it.id

def get_inventory_items():
    with get_session() as session:
        return session.query(InventoryItem).order_by(InventoryItem.id).all()

def edit_inventory_item(item_id, name, quantity, unit, cost_per_unit):
    with get_session() as session:
        it = session.get(InventoryItem, item_id)
        if not it:
            return False
        it.name = name
        it.quantity = quantity
        it.unit = unit
        it.cost_per_unit = cost_per_unit
        return True

def delete_inventory_item(item_id):
    with get_session() as session:
        it = session.get(InventoryItem, item_id)
        if it:
            session.delete(it)
            return True
    return False

# --- PDF generation ---
def generate_invoice_pdf(payment_id=None, appointment_id=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "فاتورة عيادة الأسنان")
    y -= 30

    if payment_id:
        with get_session() as session:
            payment = session.get(Payment, payment_id)
            if payment:
                appt = payment.appointment
                c.setFont("Helvetica", 11)
                c.drawString(50, y, f"تاريخ الدفع: {payment.date_paid.strftime('%Y-%m-%d %H:%M') if payment.date_paid else ''}")
                y -= 20
                if appt:
                    patient = appt.patient
                    doctor = appt.doctor
                    treatment = appt.treatment
                    c.drawString(50, y, f"المريض: {patient.name if patient else ''}")
                    y -= 15
                    c.drawString(50, y, f"الطبيب: {doctor.name if doctor else ''}")
                    y -= 15
                    c.drawString(50, y, f"العلاج: {treatment.name if treatment else ''}")
                    y -= 20

                c.drawString(50, y, f"المبلغ الإجمالي: {payment.total_amount}")
                y -= 15
                c.drawString(50, y, f"الخصم: {payment.discounts or 0.0}")
                y -= 15
                c.drawString(50, y, f"الضريبة: {payment.taxes or 0.0}")
                y -= 15
                c.drawString(50, y, f"حصة العيادة: {payment.clinic_share}")
                y -= 15
                c.drawString(50, y, f"حصة الطبيب: {payment.doctor_share}")
                y -= 15
                c.drawString(50, y, f"المدفوع: {payment.paid_amount}")
                y -= 30

    elif appointment_id:
        with get_session() as session:
            appt = session.get(Appointment, appointment_id)
            if appt:
                patient = appt.patient
                doctor = appt.doctor
                treatment = appt.treatment
                c.setFont("Helvetica", 11)
                c.drawString(50, y, f"تاريخ الموعد: {appt.date.strftime('%Y-%m-%d %H:%M') if appt.date else ''}")
                y -= 20
                c.drawString(50, y, f"المريض: {patient.name if patient else ''}")
                y -= 15
                c.drawString(50, y, f"الطبيب: {doctor.name if doctor else ''}")
                y -= 15
                c.drawString(50, y, f"العلاج: {treatment.name if treatment else ''}")
                y -= 25
                c.drawString(50, y, f"ملاحظات: {appt.notes or ''}")
                y -= 25

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- Streamlit Pages ---
def patients_page(num_cols):
    st.title("إدارة المرضى")
    with st.expander("إضافة مريض جديد", expanded=False):
        with st.form("add-patient"):
            cols = st.columns(num_cols)
            # Default variables to avoid UnboundLocalError on small screens
            name = ""
            age = 0
            gender = ""
            phone = ""
            address = ""
            medical_history = ""
            image = None

            with cols[0]:
                name = st.text_input("الاسم", value=name)
                age = st.number_input("العمر", min_value=0, step=1, value=age)

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
                    st.error("يرجى إدخال اسم المريض")
                else:
                    pid = add_patient(name=name.strip(), age=int(age), gender=gender or None,
                                      phone=phone or None, address=address or None,
                                      medical_history=medical_history or None, image=image)
                    st.success(f"تم إضافة المريض (ID: {pid})")

    st.markdown("---")
    patients = get_patients()
    df = pd.DataFrame([{
        "ID": p.id,
        "الاسم": p.name,
        "العمر": p.age,
        "الجنس": p.gender or "",
        "الهاتف": p.phone or "",
        "العنوان": p.address or ""
    } for p in patients])

    search = st.text_input("بحث (اسم، هاتف، عنوان)")
    if search:
        mask = df.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
        df = df[mask]

    st.dataframe(df, use_container_width=True)

    st.markdown("### تحرير / حذف مريض")
    ids = [p.id for p in patients]
    selected = st.selectbox("اختر ID للمريض", options=[""] + ids)
    if selected:
        pid = int(selected)
        p = get_patient(pid)
        if p:
            with st.form("edit-patient"):
                # Defaults filled from existing patient
                name = st.text_input("الاسم", value=p.name)
                age = st.number_input("العمر", min_value=0, step=1, value=p.age or 0)
                gender = st.selectbox("الجنس", ["", "ذكر", "أنثى"], index=(0 if not p.gender else (1 if p.gender == "ذكر" else 2)))
                phone = st.text_input("الهاتف", value=p.phone or "")
                address = st.text_input("العنوان", value=p.address or "")
                medical_history = st.text_area("التاريخ الطبي", value=p.medical_history or "")
                image = st.file_uploader("رفع صورة جديدة (اختياري)", type=["png", "jpg", "jpeg"])
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("حفظ التعديلات"):
                        ok = edit_patient(pid, name=name.strip(), age=int(age), gender=gender or None,
                                          phone=phone or None, address=address or None,
                                          medical_history=medical_history or None, image=image)
                        if ok:
                            st.success("تم حفظ التعديلات")
                        else:
                            st.error("حدث خطأ أثناء التعديل")
                with c2:
                    if st.button("حذف المريض"):
                        ok = delete_patient(pid)
                        if ok:
                            st.success("تم حذف المريض")
                        else:
                            st.error("فشل الحذف")

def doctors_page(num_cols):
    st.title("إدارة الأطباء")
    with st.expander("إضافة طبيب جديد", expanded=False):
        with st.form("add-doctor"):
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
                    st.error("يرجى إدخال اسم الطبيب")
                else:
                    did = add_doctor(name=name.strip(), specialty=specialty or None, phone=phone or None, email=email or None)
                    st.success(f"تم إضافة الطبيب (ID: {did})")

    st.markdown("---")
    doctors = get_doctors()
    df = pd.DataFrame([{"ID": d.id, "الاسم": d.name, "التخصص": d.specialty or "", "الهاتف": d.phone or "", "البريد": d.email or ""} for d in doctors])
    search = st.text_input("بحث في الأطباء")
    if search:
        mask = df.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
        df = df[mask]
    st.dataframe(df, use_container_width=True)

    st.markdown("### تحرير / حذف طبيب")
    ids = [d.id for d in doctors]
    selected = st.selectbox("اختر ID للطبيب", options=[""] + ids)
    if selected:
        did = int(selected)
        d = get_doctor(did)
        if d:
            with st.form("edit-doctor"):
                name = st.text_input("الاسم", value=d.name)
                specialty = st.text_input("التخصص", value=d.specialty or "")
                phone = st.text_input("الهاتف", value=d.phone or "")
                email = st.text_input("البريد", value=d.email or "")
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("حفظ التعديلات"):
                        ok = edit_doctor(did, name=name.strip(), specialty=specialty or None, phone=phone or None, email=email or None)
                        if ok:
                            st.success("تم حفظ التعديلات")
                        else:
                            st.error("حدث خطأ")
                with c2:
                    if st.button("حذف الطبيب"):
                        ok = delete_doctor(did)
                        if ok:
                            st.success("تم حذف الطبيب")
                        else:
                            st.error("فشل الحذف")

def treatments_page(num_cols):
    st.title("إدارة العلاجات")
    with st.expander("إضافة علاج جديد", expanded=False):
        with st.form("add-treatment"):
            name = ""
            base_cost = 0.0
            name = st.text_input("اسم العلاج", value=name)
            base_cost = st.number_input("السعر الأساسي", min_value=0.0, value=base_cost, step=1.0)
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("يرجى إدخال اسم العلاج")
                else:
                    tid = add_treatment(name=name.strip(), base_cost=float(base_cost))
                    st.success(f"تم إضافة العلاج (ID: {tid})")

    st.markdown("---")
    treatments = get_treatments()
    df = pd.DataFrame([{"ID": t.id, "العلاج": t.name, "السعر": t.base_cost} for t in treatments])
    st.dataframe(df, use_container_width=True)

    st.markdown("### نسب التوزيع بين العيادة والطبيب")
    doctors = get_doctors()
    treatments = get_treatments()
    if doctors and treatments:
        with st.form("set-percentage"):
            t_options = [(f"{t.id} - {t.name}", t.id) for t in treatments]
            d_options = [(f"{d.id} - {d.name}", d.id) for d in doctors]
            t_choice = st.selectbox("اختر علاج", options=[("", None)] + t_options, format_func=lambda x: x[0] if x else "")
            d_choice = st.selectbox("اختر طبيب", options=[("", None)] + d_options, format_func=lambda x: x[0] if x else "")
            clinic_perc = st.number_input("نسبة العيادة (%)", min_value=0.0, max_value=100.0, value=50.0)
            doctor_perc = st.number_input("نسبة الطبيب (%)", min_value=0.0, max_value=100.0, value=50.0)
            if st.form_submit_button("حفظ النسبة"):
                if (not t_choice) or (not d_choice) or t_choice[1] is None or d_choice[1] is None:
                    st.error("اختر علاجًا وطبيبًا")
                else:
                    set_treatment_percentage(t_choice[1], d_choice[1], float(clinic_perc), float(doctor_perc))
                    st.success("تم حفظ نسب التوزيع")
    else:
        st.info("أضف على الأقل طبيبًا وعلاجًا لإعداد النسب")

    st.markdown("### قائمة نسب التوزيع")
    tps = get_treatment_percentages()
    df2 = pd.DataFrame([{
        "ID": tp.id,
        "علاج": tp.treatment.name if tp.treatment else "",
        "طبيب": tp.doctor.name if tp.doctor else "",
        "نسبة العيادة": tp.clinic_percentage,
        "نسبة الطبيب": tp.doctor_percentage
    } for tp in tps])
    st.dataframe(df2, use_container_width=True)

def appointments_page(num_cols):
    st.title("إدارة المواعيد")
    patients = get_patients()
    doctors = get_doctors()
    treatments = get_treatments()

    with st.expander("حجز موعد جديد", expanded=False):
        with st.form("add-appointment"):
            p_options = [(f"{p.id} - {p.name}", p.id) for p in patients]
            d_options = [(f"{d.id} - {d.name}", d.id) for d in doctors]
            t_options = [(f"{t.id} - {t.name}", t.id) for t in treatments]

            p_choice = st.selectbox("اختر مريض", options=[("", None)] + p_options, format_func=lambda x: x[0] if x else "")
            d_choice = st.selectbox("اختر طبيب", options=[("", None)] + d_options, format_func=lambda x: x[0] if x else "")
            t_choice = st.selectbox("اختر علاج", options=[("", None)] + t_options, format_func=lambda x: x[0] if x else "")
            # datetime input
            date = datetime_input("تاريخ ووقت الموعد", value=datetime.datetime.now() + datetime.timedelta(days=1))
            notes = st.text_area("ملاحظات")
            if st.form_submit_button("حجز"):
                if not (p_choice and d_choice and t_choice) or p_choice[1] is None or d_choice[1] is None or t_choice[1] is None:
                    st.error("يرجى اختيار مريض وطبيب وعلاج")
                else:
                    appt_id = add_appointment(patient_id=p_choice[1], doctor_id=d_choice[1],
                                              treatment_id=t_choice[1], date=date, status="مجدول", notes=notes)
                    st.success(f"تم حجز الموعد (ID: {appt_id})")

    st.markdown("---")
    appts = get_appointments()
    df = pd.DataFrame([{
        "ID": a.id,
        "المريض": a.patient.name if a.patient else "",
        "الطبيب": a.doctor.name if a.doctor else "",
        "العلاج": a.treatment.name if a.treatment else "",
        "تاريخ": a.date,
        "الحالة": a.status
    } for a in appts])
    search = st.text_input("بحث في المواعيد")
    if search:
        mask = df.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
        df = df[mask]
    st.dataframe(df, use_container_width=True)

    st.markdown("### تحرير / حذف موعد")
    ids = [a.id for a in appts]
    selected = st.selectbox("اختر ID للموعد", options=[""] + ids)
    if selected:
        aid = int(selected)
        a = get_appointment(aid)
        if a:
            with st.form("edit-appointment"):
                p_options = [(f"{p.id} - {p.name}", p.id) for p in patients]
                d_options = [(f"{d.id} - {d.name}", d.id) for d in doctors]
                t_options = [(f"{t.id} - {t.name}", t.id) for t in treatments]
                # Determine indices safely
                def find_index(options, match_id):
                    for i, opt in enumerate(options):
                        if opt[1] == match_id:
                            return i
                    return 0
                p_default_idx = find_index(p_options, a.patient_id)
                d_default_idx = find_index(d_options, a.doctor_id)
                t_default_idx = find_index(t_options, a.treatment_id)

                p_choice = st.selectbox("المريض", options=p_options, index=p_default_idx, format_func=lambda x: x[0])
                d_choice = st.selectbox("الطبيب", options=d_options, index=d_default_idx, format_func=lambda x: x[0])
                t_choice = st.selectbox("العلاج", options=t_options, index=t_default_idx, format_func=lambda x: x[0])
                date = datetime_input("تاريخ ووقت الموعد", value=a.date or datetime.datetime.now())
                status = st.selectbox("الحالة", ["مجدول", "تم", "ملغي", "مؤجل"], index=["مجدول", "تم", "ملغي", "مؤجل"].index(a.status) if a.status in ["مجدول","تم","ملغي","مؤجل"] else 0)
                notes = st.text_area("ملاحظات", value=a.notes or "")
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("حفظ التعديلات"):
                        ok = edit_appointment(aid, patient_id=p_choice[1], doctor_id=d_choice[1],
                                              treatment_id=t_choice[1], date=date, status=status, notes=notes)
                        if ok:
                            st.success("تم حفظ التعديلات")
                        else:
                            st.error("فشل الحفظ")
                with c2:
                    if st.button("حذف الموعد"):
                        ok = delete_appointment(aid)
                        if ok:
                            st.success("تم حذف الموعد")
                        else:
                            st.error("فشل الحذف")

def payments_page(num_cols):
    st.title("الدفعات والفواتير")
    appts = get_appointments()
    payments = get_payments()

    with st.expander("تسجيل دفعة جديدة", expanded=False):
        with st.form("add-payment"):
            appt_options = [(f"{a.id} - {a.patient.name if a.patient else ''} - {a.date}", a.id) for a in appts]
            appt_choice = st.selectbox("اختر موعد (اختياري)", options=[("", None)] + appt_options, format_func=lambda x: x[0] if x else "")
            total_amount = st.number_input("المبلغ الإجمالي", min_value=0.0, value=0.0, step=1.0)
            discounts = st.number_input("الخصم", min_value=0.0, value=0.0)
            taxes = st.number_input("الضرائب", min_value=0.0, value=0.0)
            paid_amount = st.number_input("المبلغ المدفوع", min_value=0.0, value=0.0)
            payment_method = st.selectbox("طريقة الدفع", ["نقدًا", "بطاقة", "تحويل بنكي", "أخرى"])
            if st.form_submit_button("تسجيل الدفعة"):
                appt_id = appt_choice[1] if appt_choice else None
                pid = add_payment(appointment_id=appt_id, total_amount=float(total_amount),
                                  paid_amount=float(paid_amount), payment_method=payment_method,
                                  discounts=float(discounts), taxes=float(taxes))
                st.success(f"تم تسجيل الدفعة (ID: {pid})")

    st.markdown("---")
    df = pd.DataFrame([{
        "ID": p.id,
        "تاريخ الدفع": p.date_paid,
        "المبلغ الإجمالي": p.total_amount,
        "المدفوع": p.paid_amount,
        "حصة العيادة": p.clinic_share,
        "حصة الطبيب": p.doctor_share,
        "طريقة الدفع": p.payment_method,
        "موعد/ID": p.appointment_id
    } for p in payments])
    st.dataframe(df, use_container_width=True)

    st.markdown("### طباعة فاتورة PDF")
    ids = [p.id for p in payments]
    sel = st.selectbox("اختر ID للدفعة للطباعة", options=[""] + ids)
    if sel:
        pid = int(sel)
        buf = generate_invoice_pdf(payment_id=pid)
        st.download_button("تحميل الفاتورة PDF", data=buf, file_name=f"invoice_payment_{pid}.pdf", mime="application/pdf")

def expenses_page(num_cols):
    st.title("المصروفات")
    with st.expander("إضافة مصروف", expanded=False):
        with st.form("add-expense"):
            desc = st.text_input("البيان")
            amount = st.number_input("المبلغ", min_value=0.0, value=0.0)
            date = st.date_input("التاريخ", value=datetime.date.today())
            if st.form_submit_button("إضافة"):
                add_expense(description=desc or None, amount=float(amount), date=datetime.datetime.combine(date, datetime.datetime.min.time()))
                st.success("تم إضافة المصروف")

    st.markdown("---")
    expenses = get_expenses()
    df = pd.DataFrame([{"ID": e.id, "البيان": e.description, "المبلغ": e.amount, "التاريخ": e.date} for e in expenses])
    st.dataframe(df, use_container_width=True)

    st.markdown("### حذف مصروف")
    ids = [e.id for e in expenses]
    sel = st.selectbox("اختر ID للمصروف", options=[""] + ids)
    if sel:
        eid = int(sel)
        if st.button("حذف المصروف"):
            ok = delete_expense(eid)
            if ok:
                st.success("تم حذف المصروف")
            else:
                st.error("فشل الحذف")

def inventory_page(num_cols):
    st.title("إدارة المخزون")
    with st.expander("إضافة بند جديد", expanded=False):
        with st.form("add-inventory"):
            name = st.text_input("اسم الصنف")
            quantity = st.number_input("الكمية", min_value=0.0, value=0.0)
            unit = st.text_input("الوحدة (مثال: قطعة، علبة)")
            cost_per_unit = st.number_input("تكلفة الوحدة", min_value=0.0, value=0.0)
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("أدخل اسم الصنف")
                else:
                    iid = add_inventory_item(name=name.strip(), quantity=float(quantity), unit=unit or None, cost_per_unit=float(cost_per_unit))
                    st.success(f"تم إضافة الصنف (ID: {iid})")

    st.markdown("---")
    items = get_inventory_items()
    df = pd.DataFrame([{"ID": it.id, "الاسم": it.name, "الكمية": it.quantity, "الوحدة": it.unit, "تكلفة الوحدة": it.cost_per_unit} for it in items])
    st.dataframe(df, use_container_width=True)

    st.markdown("### تعديل / حذف بند مخزون")
    ids = [it.id for it in items]
    sel = st.selectbox("اختر ID للصنف", options=[""] + ids)
    if sel:
        iid = int(sel)
        it = next((x for x in items if x.id == iid), None)
        if it:
            with st.form("edit-inv"):
                name = st.text_input("الاسم", value=it.name)
                quantity = st.number_input("الكمية", min_value=0.0, value=it.quantity)
                unit = st.text_input("الوحدة", value=it.unit or "")
                cost_per_unit = st.number_input("تكلفة الوحدة", min_value=0.0, value=it.cost_per_unit)
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("حفظ التعديلات"):
                        ok = edit_inventory_item(iid, name=name.strip(), quantity=float(quantity), unit=unit or None, cost_per_unit=float(cost_per_unit))
                        if ok:
                            st.success("تم حفظ التعديلات")
                        else:
                            st.error("فشل الحفظ")
                with c2:
                    if st.button("حذف الصنف"):
                        ok = delete_inventory_item(iid)
                        if ok:
                            st.success("تم حذف الصنف")
                        else:
                            st.error("فشل الحذف")

def reports_page(num_cols):
    st.title("التقارير المالية")
    payments = get_payments()
    expenses = get_expenses()

    df_pay = pd.DataFrame([{
        "تاريخ": p.date_paid.date() if p.date_paid else None,
        "clinic_share": p.clinic_share or 0.0,
        "doctor_share": p.doctor_share or 0.0,
        "total": p.total_amount or 0.0
    } for p in payments]) if payments else pd.DataFrame()

    df_exp = pd.DataFrame([{
        "تاريخ": e.date.date() if e.date else None,
        "amount": e.amount or 0.0
    } for e in expenses]) if expenses else pd.DataFrame()

    st.markdown("### ملخص عام")
    total_income = df_pay["total"].sum() if not df_pay.empty else 0.0
    total_clinic = df_pay["clinic_share"].sum() if not df_pay.empty else 0.0
    total_doctor = df_pay["doctor_share"].sum() if not df_pay.empty else 0.0
    total_expenses = df_exp["amount"].sum() if not df_exp.empty else 0.0
    net_profit = total_clinic - total_expenses

    st.metric("إجمالي الإيرادات", f"{total_income:.2f}")
    st.metric("حصة العيادة الإجمالية", f"{total_clinic:.2f}")
    st.metric("حصة الأطباء الإجمالية", f"{total_doctor:.2f}")
    st.metric("إجمالي المصروفات", f"{total_expenses:.2f}")
    st.metric("ربح / خسارة صافي (حصة العيادة - المصروفات)", f"{net_profit:.2f}")

    st.markdown("---")
    st.markdown("### رسوم/مصاريف حسب التاريخ")
    if not df_pay.empty:
        df_agg = df_pay.groupby("تاريخ").sum().reset_index().sort_values("تاريخ")
        fig = px.line(df_agg, x="تاريخ", y=["clinic_share", "doctor_share"], title="حصة العيادة مقابل حصة الأطباء عبر الزمن")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد دفعات لعرض المخططات")

    if not df_exp.empty:
        df_e_agg = df_exp.groupby("تاريخ").sum().reset_index().sort_values("تاريخ")
        fig2 = px.bar(df_e_agg, x="تاريخ", y="amount", title="المصروفات عبر الزمن")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("لا توجد مصروفات لعرض المخططات")

    st.markdown("---")
    st.markdown("### تقارير قابلة للتحميل")
    if payments:
        df_all = pd.DataFrame([{
            "date_paid": p.date_paid,
            "total_amount": p.total_amount,
            "paid_amount": p.paid_amount,
            "clinic_share": p.clinic_share,
            "doctor_share": p.doctor_share
        } for p in payments])
        buf = io.BytesIO()
        buf.write(df_all.to_csv(index=False).encode("utf-8"))
        buf.seek(0)
        st.download_button("تحميل ملخص الدفعات (CSV)", data=buf, file_name="payments_summary.csv", mime="text/csv")
    else:
        st.info("لا توجد دفعات للتصدير")

# --- Main ---
def main():
    st.set_page_config(page_title="عيادة الأسنان", layout="wide", page_icon="🦷")
    width = get_screen_width()
    num_cols = determine_num_columns(width)

    st.sidebar.title("القائمة")
    page = st.sidebar.selectbox("القسم", [
        "إدارة المرضى",
        "إدارة الأطباء",
        "إدارة العلاجات",
        "إدارة المواعيد",
        "إدارة المخزون",
        "الدفعات",
        "المصروفات",
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
    elif page == "إدارة المخزون":
        inventory_page(num_cols)
    elif page == "الدفعات":
        payments_page(num_cols)
    elif page == "المصروفات":
        expenses_page(num_cols)
    elif page == "التقارير":
        reports_page(num_cols)
    else:
        st.write("اختر صفحة من القائمة الجانبية")

if __name__ == "__main__":
    main()
