# ---------------------------------------------------------
# 🦷 Dental Clinic Management System - v2
# المرحلة الأولى: إعداد الواجهة والقاعدة
# ---------------------------------------------------------

import streamlit as st
import pandas as pd
import datetime
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import plotly.express as px
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ---------------------------------------------------------
#  إعداد الصفحة والستايل الأبيض
# ---------------------------------------------------------
st.set_page_config(
    page_title="عيادة الأسنان",
    page_icon="🦷",
    layout="wide",
)

# 🎨 CSS لتصميم أبيض بالكامل
st.markdown("""
    <style>
        .stApp {
            background-color: white;
        }
        body, p, label, span, div {
            color: #000000 !important;
            font-family: "Cairo", sans-serif !important;
        }
        .stTextInput>div>div>input,
        .stTextArea>div>div>textarea,
        .stSelectbox>div>div>div>div,
        .stNumberInput>div>div>input {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 1px solid #CCCCCC !important;
        }
        button[kind="primary"] {
            background-color: #0078D7 !important;
            color: white !important;
            border-radius: 6px !important;
        }
        button[kind="primary"]:hover {
            background-color: #005fa3 !important;
        }
        .stDataFrame {
            background-color: #FFFFFF !important;
        }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
#  إعداد قاعدة البيانات
# ---------------------------------------------------------
Base = declarative_base()
engine = create_engine('sqlite:///dental_clinic_v2.db', echo=False)
Session = sessionmaker(bind=engine)

# ---------------------------------------------------------
#  نماذج الجداول (Models)
# ---------------------------------------------------------
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
    appointment_id = Column(Integer, ForeignKey('appointments.id'))
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

class Supplier(Base):
    __tablename__ = 'suppliers'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String)  # مثل "معمل", "مورد خامات"
    phone = Column(String)
    email = Column(String)
    address = Column(String)

class SupplierInvoice(Base):
    __tablename__ = 'supplier_invoices'
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'))
    description = Column(String)
    amount = Column(Float)
    date = Column(DateTime)
    paid = Column(Float)
    supplier = relationship("Supplier")

# إنشاء الجداول في قاعدة البيانات
Base.metadata.create_all(engine)
# ---------------------------------------------------------
# الجزء الثاني: دوال الجلسة (session) و CRUD وواجهة المرضى
# ---------------------------------------------------------

from contextlib import contextmanager

# ---------------------------
# مساعد جلسة آمن (transaction scope)
# ---------------------------
@contextmanager
def session_scope():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

# ---------------------------
# Utilities بسيطة
# ---------------------------
import io, uuid

IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)

def secure_filename(filename):
    base, ext = os.path.splitext(filename) if filename else ("file", ".png")
    return f"{uuid.uuid4().hex}{ext}"

def save_uploaded_file(uploaded_file, prefix="file"):
    """يحفظ الملف المرفوع ويعيد المسار أو None"""
    if uploaded_file is None:
        return None
    filename = secure_filename(getattr(uploaded_file, "name", None))
    path = os.path.join(IMAGES_DIR, f"{prefix}_{filename}")
    with open(path, "wb") as f:
        f.write(uploaded_file.getvalue())
    return path

def format_money(x):
    try:
        return f"{float(x):,.2f} جنيه"
    except Exception:
        return f"0.00 جنيه"

# ---------------------------
# CRUD - Patients
# ---------------------------
def add_patient(name, age=None, gender=None, phone=None, address=None, medical_history=None, image=None):
    with session_scope() as s:
        p = Patient(name=name, age=age, gender=gender, phone=phone, address=address, medical_history=medical_history)
        if image:
            p.image_path = save_uploaded_file(image, prefix="patient")
        s.add(p)
        s.flush()
        return p.id

def edit_patient(patient_id, name=None, age=None, gender=None, phone=None, address=None, medical_history=None, image=None):
    with session_scope() as s:
        p = s.get(Patient, patient_id)
        if not p:
            return False
        if name is not None: p.name = name
        if age is not None: p.age = age
        if gender is not None: p.gender = gender
        if phone is not None: p.phone = phone
        if address is not None: p.address = address
        if medical_history is not None: p.medical_history = medical_history
        if image:
            p.image_path = save_uploaded_file(image, prefix="patient")
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
        result = []
        for r in rows:
            result.append({
                "id": r.id,
                "name": r.name,
                "age": r.age,
                "gender": r.gender,
                "phone": r.phone,
                "address": r.address,
                "medical_history": r.medical_history,
                "image_path": r.image_path
            })
        return result

# ---------------------------
# CRUD - Doctors
# ---------------------------
def add_doctor(name, specialty=None, phone=None, email=None):
    with session_scope() as s:
        d = Doctor(name=name, specialty=specialty, phone=phone, email=email)
        s.add(d); s.flush(); return d.id

def edit_doctor(doctor_id, name=None, specialty=None, phone=None, email=None):
    with session_scope() as s:
        d = s.get(Doctor, doctor_id)
        if not d: return False
        if name: d.name = name
        if specialty: d.specialty = specialty
        if phone: d.phone = phone
        if email: d.email = email
        return True

def get_doctors():
    with session_scope() as s:
        rows = s.query(Doctor).order_by(Doctor.id).all()
        return [{"id": r.id, "name": r.name, "specialty": r.specialty, "phone": r.phone, "email": r.email} for r in rows]

# ---------------------------
# CRUD - Treatments & percentages
# ---------------------------
def add_treatment(name, base_cost=0.0):
    with session_scope() as s:
        t = Treatment(name=name, base_cost=base_cost)
        s.add(t); s.flush(); return t.id

def get_treatments():
    with session_scope() as s:
        rows = s.query(Treatment).order_by(Treatment.id).all()
        return [{"id": r.id, "name": r.name, "base_cost": r.base_cost} for r in rows]

def set_treatment_percentage(treatment_id, doctor_id, clinic_percentage, doctor_percentage):
    with session_scope() as s:
        tp = s.query(TreatmentPercentage).filter_by(treatment_id=treatment_id, doctor_id=doctor_id).first()
        if not tp:
            tp = TreatmentPercentage(treatment_id=treatment_id, doctor_id=doctor_id, clinic_percentage=clinic_percentage, doctor_percentage=doctor_percentage)
            s.add(tp)
        else:
            tp.clinic_percentage = clinic_percentage
            tp.doctor_percentage = doctor_percentage
        s.flush(); return True

def get_treatment_percentages():
    with session_scope() as s:
        rows = s.query(TreatmentPercentage).all()
        out = []
        for r in rows:
            out.append({
                "id": r.id,
                "treatment_id": r.treatment_id,
                "treatment_name": r.treatment.name if r.treatment else None,
                "doctor_id": r.doctor_id,
                "doctor_name": r.doctor.name if r.doctor else None,
                "clinic_percentage": r.clinic_percentage,
                "doctor_percentage": r.doctor_percentage
            })
        return out

# ---------------------------
# CRUD - Appointments
# ---------------------------
def add_appointment(patient_id, doctor_id, treatment_id, date, status="مجدول", notes=None):
    with session_scope() as s:
        a = Appointment(patient_id=patient_id, doctor_id=doctor_id, treatment_id=treatment_id, date=date, status=status, notes=notes)
        s.add(a); s.flush(); return a.id

def get_appointments():
    with session_scope() as s:
        rows = s.query(Appointment).order_by(Appointment.date.desc()).all()
        out = []
        for r in rows:
            out.append({
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
        return out

# ---------------------------
# CRUD - Payments
# ---------------------------
def calculate_shares(appointment_id, total_amount, discounts=0.0, taxes=0.0):
    """يحسب نسبة العيادة والطبيب باستخدام جدول النسب إن وجد"""
    with session_scope() as s:
        appointment = s.get(Appointment, appointment_id) if appointment_id else None
        if appointment:
            tp = s.query(TreatmentPercentage).filter_by(treatment_id=appointment.treatment_id, doctor_id=appointment.doctor_id).first()
            if tp:
                clinic_perc = tp.clinic_percentage or 50.0
                doctor_perc = tp.doctor_percentage or 50.0
            else:
                clinic_perc = doctor_perc = 50.0
        else:
            clinic_perc = doctor_perc = 50.0
    net = float(total_amount) - float(discounts or 0.0) + float(taxes or 0.0)
    clinic = round(net * clinic_perc / 100.0, 2)
    doctor = round(net * doctor_perc / 100.0, 2)
    return clinic, doctor

def add_payment(appointment_id, total_amount, paid_amount, payment_method, discounts=0.0, taxes=0.0):
    clinic_share, doctor_share = calculate_shares(appointment_id, total_amount, discounts, taxes)
    with session_scope() as s:
        p = Payment(appointment_id=appointment_id, total_amount=total_amount, paid_amount=paid_amount, clinic_share=clinic_share, doctor_share=doctor_share, payment_method=payment_method, discounts=discounts, taxes=taxes, date_paid=datetime.datetime.now())
        s.add(p); s.flush(); return p.id

def get_payments():
    with session_scope() as s:
        rows = s.query(Payment).order_by(Payment.date_paid.desc()).all()
        return [{"id": r.id, "appointment_id": r.appointment_id, "total_amount": r.total_amount, "paid_amount": r.paid_amount, "clinic_share": r.clinic_share, "doctor_share": r.doctor_share, "payment_method": r.payment_method, "discounts": r.discounts, "taxes": r.taxes, "date_paid": r.date_paid} for r in rows]

# ---------------------------
# CRUD - Expenses
# ---------------------------
def add_expense(description, amount, date=None):
    if date is None: date = datetime.datetime.now()
    with session_scope() as s:
        e = Expense(description=description, amount=amount, date=date)
        s.add(e); s.flush(); return e.id

def get_expenses():
    with session_scope() as s:
        rows = s.query(Expense).order_by(Expense.date.desc()).all()
        return [{"id": r.id, "description": r.description, "amount": r.amount, "date": r.date} for r in rows]

# ---------------------------
# CRUD - Suppliers & Invoices
# ---------------------------
def add_supplier(name, category=None, phone=None, email=None, address=None):
    with session_scope() as s:
        sup = Supplier(name=name, category=category, phone=phone, email=email, address=address)
        s.add(sup); s.flush(); return sup.id

def get_suppliers():
    with session_scope() as s:
        rows = s.query(Supplier).order_by(Supplier.id).all()
        return [{"id": r.id, "name": r.name, "category": r.category, "phone": r.phone, "email": r.email, "address": r.address} for r in rows]

def add_supplier_invoice(supplier_id, description, amount, date=None, paid=0.0):
    if date is None: date = datetime.datetime.now()
    with session_scope() as s:
        inv = SupplierInvoice(supplier_id=supplier_id, description=description, amount=amount, date=date, paid=paid)
        s.add(inv); s.flush(); return inv.id

def get_supplier_invoices(supplier_id):
    with session_scope() as s:
        rows = s.query(SupplierInvoice).filter_by(supplier_id=supplier_id).order_by(SupplierInvoice.date.desc()).all()
        return [{"id": r.id, "description": r.description, "amount": r.amount, "date": r.date, "paid": r.paid} for r in rows]

# ---------------------------
# صفحة إدارة المرضى (واجهة Streamlit)
# ---------------------------
def patients_page():
    st.header("إدارة المرضى")
    with st.expander("إضافة مريض جديد", expanded=True):
        with st.form("form_add_patient"):
            c1, c2, c3 = st.columns(3)
            with c1:
                name = st.text_input("الاسم")
                age = st.number_input("العمر", min_value=0, value=0)
            with c2:
                gender = st.selectbox("الجنس", ["", "ذكر", "أنثى"])
                phone = st.text_input("الهاتف")
            with c3:
                address = st.text_input("العنوان")
                image = st.file_uploader("صورة المريض (اختياري)", type=["png","jpg","jpeg"])
            medical_history = st.text_area("التاريخ الطبي")
            if st.form_submit_button("إضافة مريض"):
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

    st.markdown("### تفاصيل مريض")
    ids = [p["id"] for p in patients] if patients else []
    sel = st.selectbox("اختر ID المريض", options=[""] + ids)
    if sel:
        pid = int(sel)
        p = next((x for x in patients if x["id"] == pid), None)
        if p:
            st.subheader(p["name"])
            st.write(f"العمر: {p['age']} — الجنس: {p['gender'] or '-'} — الهاتف: {p['phone'] or '-'}")
            st.write("التاريخ الطبي:"); st.write(p["medical_history"] or "-")
            # زر لتحرير أو حذف
            if st.button("حذف المريض"):
                if delete_patient(pid):
                    st.success("تم الحذف")
                    st.experimental_rerun()
                else:
                    st.error("فشل الحذف")
            # تحرير
            if st.button("تحرير المريض"):
                with st.form("edit_patient_form"):
                    name2 = st.text_input("الاسم", value=p["name"])
                    age2 = st.number_input("العمر", value=p["age"] or 0)
                    gender2 = st.selectbox("الجنس", ["", "ذكر", "أنثى"], index=0 if not p["gender"] else (1 if p["gender"]=="ذكر" else 2))
                    phone2 = st.text_input("الهاتف", value=p["phone"] or "")
                    address2 = st.text_input("العنوان", value=p["address"] or "")
                    med2 = st.text_area("التاريخ الطبي", value=p["medical_history"] or "")
                    img2 = st.file_uploader("رفع صورة جديدة (اختياري)", type=["png","jpg","jpeg"])
                    if st.form_submit_button("حفظ التعديلات"):
                        ok = edit_patient(pid, name=name2.strip(), age=int(age2), gender=gender2 or None, phone=phone2 or None, address=address2 or None, medical_history=med2 or None, image=img2)
                        if ok:
                            st.success("تم حفظ التعديلات")
                            st.experimental_rerun()
                        else:
                            st.error("فشل الحفظ")
# ---------------------------------------------------------
# الجزء الثالث: صفحات إدارة الأطباء والعلاجات والمواعيد والمدفوعات والموردين والتقارير
# ---------------------------------------------------------

# -----------------------------------
# صفحة الأطباء
# -----------------------------------
def doctors_page():
    st.header("إدارة الأطباء")
    with st.expander("إضافة طبيب جديد", expanded=True):
        with st.form("add_doctor_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                name = st.text_input("الاسم")
            with c2:
                specialty = st.text_input("التخصص")
            with c3:
                phone = st.text_input("الهاتف")
            email = st.text_input("البريد الإلكتروني")
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("الاسم مطلوب")
                else:
                    did = add_doctor(name, specialty, phone, email)
                    st.success(f"تمت إضافة الطبيب (ID: {did})")

    doctors = get_doctors()
    df = pd.DataFrame(doctors)
    st.dataframe(df, use_container_width=True)

# -----------------------------------
# صفحة العلاجات والنسب
# -----------------------------------
def treatments_page():
    st.header("إدارة العلاجات والنسب")
    with st.expander("إضافة علاج جديد", expanded=True):
        with st.form("add_treatment_form"):
            name = st.text_input("اسم العلاج")
            base_cost = st.number_input("التكلفة الأساسية", min_value=0.0, value=0.0, step=10.0)
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("الاسم مطلوب")
                else:
                    tid = add_treatment(name, base_cost)
                    st.success(f"تمت إضافة العلاج (ID: {tid})")

    treatments = get_treatments()
    st.dataframe(pd.DataFrame(treatments), use_container_width=True)

    st.markdown("### تحديد نسب الطبيب والعيادة")
    doctors = get_doctors()
    if doctors and treatments:
        doctor_sel = st.selectbox("اختر الطبيب", [d["name"] for d in doctors])
        treatment_sel = st.selectbox("اختر العلاج", [t["name"] for t in treatments])
        d_id = next(d["id"] for d in doctors if d["name"] == doctor_sel)
        t_id = next(t["id"] for t in treatments if t["name"] == treatment_sel)
        clinic_perc = st.slider("نسبة العيادة %", 0, 100, 50)
        doctor_perc = 100 - clinic_perc
        if st.button("حفظ النسب"):
            set_treatment_percentage(t_id, d_id, clinic_perc, doctor_perc)
            st.success("تم حفظ النسب بنجاح")
    st.markdown("### جميع النسب الحالية")
    st.dataframe(pd.DataFrame(get_treatment_percentages()), use_container_width=True)

# -----------------------------------
# صفحة المواعيد
# -----------------------------------
def appointments_page():
    st.header("إدارة المواعيد")
    patients = get_patients()
    doctors = get_doctors()
    treatments = get_treatments()

    with st.expander("إضافة موعد جديد", expanded=True):
        with st.form("add_appointment_form"):
            patient_name = st.selectbox("المريض", [p["name"] for p in patients]) if patients else st.warning("لا يوجد مرضى")
            doctor_name = st.selectbox("الطبيب", [d["name"] for d in doctors]) if doctors else st.warning("لا يوجد أطباء")
            treatment_name = st.selectbox("العلاج", [t["name"] for t in treatments]) if treatments else st.warning("لا يوجد علاجات")
            date = st.date_input("التاريخ", datetime.date.today())
            notes = st.text_area("ملاحظات")
            if st.form_submit_button("إضافة"):
                pid = next(p["id"] for p in patients if p["name"] == patient_name)
                did = next(d["id"] for d in doctors if d["name"] == doctor_name)
                tid = next(t["id"] for t in treatments if t["name"] == treatment_name)
                aid = add_appointment(pid, did, tid, date, "مجدول", notes)
                st.success(f"تمت إضافة الموعد (ID: {aid})")

    appts = get_appointments()
    df = pd.DataFrame(appts)
    if not df.empty:
        df["date"] = df["date"].astype(str)
    st.dataframe(df, use_container_width=True)

# -----------------------------------
# صفحة المدفوعات والإدخال اليومي
# -----------------------------------
def payments_page():
    st.header("الإدخال اليومي والمدفوعات")

    appts = get_appointments()
    if not appts:
        st.warning("لا توجد مواعيد")
        return

    with st.expander("إضافة دفعة جديدة", expanded=True):
        with st.form("add_payment_form"):
            appt_name = st.selectbox("اختر الموعد", [f"{a['id']} - {a['patient_name']} ({a['treatment_name']})" for a in appts])
            total = st.number_input("إجمالي المبلغ", min_value=0.0, value=0.0)
            paid = st.number_input("المبلغ المدفوع", min_value=0.0, value=0.0)
            discounts = st.number_input("الخصومات", min_value=0.0, value=0.0)
            taxes = st.number_input("الضرائب", min_value=0.0, value=0.0)
            pay_method = st.selectbox("طريقة الدفع", ["نقدي", "بطاقة", "تحويل بنكي"])
            if st.form_submit_button("إضافة"):
                aid = int(appt_name.split(" - ")[0])
                pid = add_payment(aid, total, paid, pay_method, discounts, taxes)
                st.success(f"تمت إضافة الدفعة (ID: {pid})")

    payments = get_payments()
    df = pd.DataFrame(payments)
    if not df.empty:
        df["clinic_share"] = df["clinic_share"].apply(format_money)
        df["doctor_share"] = df["doctor_share"].apply(format_money)
        df["total_amount"] = df["total_amount"].apply(format_money)
        df["paid_amount"] = df["paid_amount"].apply(format_money)
    st.dataframe(df, use_container_width=True)

# -----------------------------------
# صفحة المصروفات
# -----------------------------------
def expenses_page():
    st.header("المصروفات اليومية")
    with st.expander("إضافة مصروف جديد", expanded=True):
        with st.form("add_expense_form"):
            desc = st.text_input("الوصف")
            amount = st.number_input("المبلغ", min_value=0.0, value=0.0)
            if st.form_submit_button("إضافة"):
                if not desc.strip():
                    st.error("الوصف مطلوب")
                else:
                    eid = add_expense(desc, amount)
                    st.success(f"تمت إضافة المصروف (ID: {eid})")

    expenses = get_expenses()
    df = pd.DataFrame(expenses)
    if not df.empty:
        df["amount"] = df["amount"].apply(format_money)
    st.dataframe(df, use_container_width=True)

# -----------------------------------
# صفحة الموردين والفواتير
# -----------------------------------
def suppliers_page():
    st.header("حسابات الموردين والمعامل")

    with st.expander("إضافة مورد جديد", expanded=True):
        with st.form("add_supplier_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                name = st.text_input("الاسم")
            with c2:
                category = st.selectbox("الفئة", ["معمل", "مواد خام", "أخرى"])
            with c3:
                phone = st.text_input("الهاتف")
            email = st.text_input("البريد الإلكتروني")
            address = st.text_input("العنوان")
            if st.form_submit_button("إضافة"):
                if not name.strip():
                    st.error("الاسم مطلوب")
                else:
                    sid = add_supplier(name, category, phone, email, address)
                    st.success(f"تمت إضافة المورد (ID: {sid})")

    suppliers = get_suppliers()
    df = pd.DataFrame(suppliers)
    st.dataframe(df, use_container_width=True)

    st.markdown("### فواتير المورد")
    ids = [s["id"] for s in suppliers]
    if ids:
        sel = st.selectbox("اختر المورد", options=[""] + ids)
        if sel:
            sid = int(sel)
            with st.form("add_invoice_form"):
                desc = st.text_input("الوصف")
                amount = st.number_input("المبلغ", min_value=0.0, value=0.0)
                paid = st.number_input("المدفوع", min_value=0.0, value=0.0)
                if st.form_submit_button("إضافة فاتورة"):
                    iid = add_supplier_invoice(sid, desc, amount, None, paid)
                    st.success(f"تمت إضافة الفاتورة (ID: {iid})")

            invoices = get_supplier_invoices(sid)
            df2 = pd.DataFrame(invoices)
            if not df2.empty:
                df2["amount"] = df2["amount"].apply(format_money)
                df2["paid"] = df2["paid"].apply(format_money)
            st.dataframe(df2, use_container_width=True)

# -----------------------------------
# صفحة التقارير والملخص اليومي
# -----------------------------------
def reports_page():
    st.header("📊 التقارير اليومية والمالية")

    payments = get_payments()
    expenses = get_expenses()
    dfp = pd.DataFrame(payments)
    dfe = pd.DataFrame(expenses)

    today = datetime.date.today()
    today_payments = dfp[dfp["date_paid"].dt.date == today] if not dfp.empty else pd.DataFrame()
    today_expenses = dfe[dfe["date"].dt.date == today] if not dfe.empty else pd.DataFrame()

    total_income = today_payments["paid_amount"].sum() if not today_payments.empty else 0
    total_exp = today_expenses["amount"].sum() if not today_expenses.empty else 0
    net = total_income - total_exp

    st.metric("إجمالي الدخل اليومي", format_money(total_income))
    st.metric("إجمالي المصروفات", format_money(total_exp))
    st.metric("صافي الربح", format_money(net))

    st.markdown("### 🔹 تفاصيل الدخل")
    if not today_payments.empty:
        st.dataframe(today_payments[["id","appointment_id","paid_amount","clinic_share","doctor_share","payment_method"]])
    else:
        st.info("لا يوجد دخل اليوم")

    st.markdown("### 🔹 تفاصيل المصروفات")
    if not today_expenses.empty:
        st.dataframe(today_expenses)
    else:
        st.info("لا توجد مصروفات اليوم")

# -----------------------------------
# واجهة التنقل الرئيسية
# -----------------------------------
def main():
    st.set_page_config(page_title="Dental Clinic Management", layout="wide")
    st.markdown(
        """
        <style>
        body, .stApp, div[data-testid="stVerticalBlock"] {
            background-color: white !important;
            color: black !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    menu = st.sidebar.radio(
        "📁 اختر الصفحة",
        [
            "المرضى",
            "الأطباء",
            "العلاجات",
            "المواعيد",
            "المدفوعات",
            "المصروفات",
            "الموردين",
            "التقارير",
        ]
    )

    if menu == "المرضى": patients_page()
    elif menu == "الأطباء": doctors_page()
    elif menu == "العلاجات": treatments_page()
    elif menu == "المواعيد": appointments_page()
    elif menu == "المدفوعات": payments_page()
    elif menu == "المصروفات": expenses_page()
    elif menu == "الموردين": suppliers_page()
    elif menu == "التقارير": reports_page()


if __name__ == "__main__":
    main()                            
