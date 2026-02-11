# app.py - Main Flask application for GarderieFlow API

from flask import Flask, jsonify, request, g
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from sqlalchemy.dialects.postgresql import ENUM
from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash, check_password_hash
import os
import logging
from functools import wraps
from sqlalchemy import func, extract
from flask_cors import CORS


app = Flask(__name__)
CORS(app, supports_credentials=True)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your-secret-key')  # Change in production

db = SQLAlchemy(app)
jwt = JWTManager(app)

# Logging
logging.basicConfig(level=logging.INFO)

# Enums
gender_enum = ENUM('M', 'F', 'Autre', 'Non renseigné', name='gender_enum', create_type=False)
student_status_enum = ENUM('actif', 'quitté', 'archivé', name='student_status_enum', create_type=False)
contact_type_enum = ENUM('téléphone', 'mobile', 'email', 'whatsapp', 'autre', name='contact_type_enum', create_type=False)
relation_enum = ENUM('père', 'mère', 'grand-parent', 'tuteur', 'autre', name='relation_enum', create_type=False)
enrollment_status_enum = ENUM('actif', 'expiré', 'renouvelé', 'résilié', name='enrollment_status_enum', create_type=False)
transaction_type_enum = ENUM('gain', 'dépense', name='transaction_type_enum', create_type=False)
payment_method_enum = ENUM('espèces', 'virement', 'carte', 'mobile money', 'autre', name='payment_method_enum', create_type=False)
attendance_status_enum = ENUM('présent', 'absent', 'justifié', name='attendance_status_enum', create_type=False)

# Models
class Organization(db.Model):
    __tablename__ = 'organizations'
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(255), nullable=False)
    manager_name = db.Column(db.String(100), nullable=False)
    manager_lastname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    birthdate = db.Column(db.Date)
    logo_url = db.Column(db.String(500))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    photo_url = db.Column(db.String(500))
    birthdate = db.Column(db.Date, nullable=False)
    gender = db.Column(gender_enum, default='Non renseigné')
    school = db.Column(db.String(255))
    inscription_date = db.Column(db.Date, nullable=False)
    leave_date = db.Column(db.Date)
    status = db.Column(student_status_enum, default='actif')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class ParentContact(db.Model):
    __tablename__ = 'parent_contacts'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(contact_type_enum, nullable=False)
    value = db.Column(db.String(255), nullable=False)
    is_principal = db.Column(db.Boolean, default=False)
    firstname = db.Column(db.String(100))
    lastname = db.Column(db.String(100))
    relation = db.Column(relation_enum, default='autre')
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(enrollment_status_enum, default='actif')
    notified_at = db.Column(db.DateTime(timezone=True))
    terminated_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class TransactionCategory(db.Model):
    __tablename__ = 'transaction_categories'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    label = db.Column(db.String(255), nullable=False)
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('organization_id', 'label'),)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='SET NULL'))
    date = db.Column(db.Date, nullable=False)
    type = db.Column(transaction_type_enum, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(payment_method_enum, nullable=False)
    reference = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey('transaction_categories.id', ondelete='SET NULL'))
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(attendance_status_enum, default='absent')
    arrival_time = db.Column(db.Time)
    departure_time = db.Column(db.Time)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('student_id', 'date'),)

# Helper function to serialize dates and times
def serialize_date(obj):
    if isinstance(obj, date):
        return obj.isoformat()
    return None

def serialize_time(obj):
    if obj:
        return obj.isoformat(timespec='minutes')
    return None

# Decorator for organization scoping
def org_scoped(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        current_user = get_jwt_identity()
        g.org_id = int(current_user)
        return f(*args, **kwargs)
    return decorated

# Authentication Routes
@app.route('/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    org = Organization.query.filter_by(email=email).first()
    if org and check_password_hash(org.password_hash, password):
        access_token = access_token = create_access_token(
    identity=str(org.id),  
    additional_claims={
        "email": org.email
    }
)

        return jsonify(access_token=access_token), 200
    return jsonify(message='Invalid credentials'), 401

@app.route('/auth/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    if Organization.query.filter_by(email=email).first():
        return jsonify(message='Email already exists'), 409
    hashed_pw = generate_password_hash(data.get('password'))
    birthdate = datetime.fromisoformat(data.get('birthdate')).date() if data.get('birthdate') else None
    org = Organization(
        company_name=data.get('company_name'),
        manager_name=data.get('manager_name'),
        manager_lastname=data.get('manager_lastname'),
        email=email,
        password_hash=hashed_pw,
        birthdate=birthdate,
        logo_url=data.get('logo_url'),
        address=data.get('address')
    )
    db.session.add(org)
    db.session.commit()
    return jsonify(message='Registered successfully'), 201

# Students Management
@app.route('/students', methods=['GET'])
@org_scoped
def get_students():
    status = request.args.get('status')
    search = request.args.get('search')
    query = Student.query.filter_by(organization_id=g.org_id)
    if status:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(
            db.or_(
                Student.firstname.ilike(f'%{search}%'),
                Student.lastname.ilike(f'%{search}%')
            )
        )
    students = query.all()
    return jsonify([{
        'id': s.id,
        'firstname': s.firstname,
        'lastname': s.lastname,
        'age': (datetime.now().date() - s.birthdate).days // 365 if s.birthdate else None,
        'status': s.status,
        'inscription_date': serialize_date(s.inscription_date)
    } for s in students])

@app.route('/students', methods=['POST'])
@org_scoped
def add_student():
    data = request.json
    birthdate = datetime.fromisoformat(data['birthdate']).date()
    inscription_date = datetime.fromisoformat(data['inscription_date']).date()
    leave_date = datetime.fromisoformat(data['leave_date']).date() if data.get('leave_date') else None
    student = Student(
        organization_id=g.org_id,
        firstname=data['firstname'],
        lastname=data['lastname'],
        photo_url=data.get('photo_url'),
        birthdate=birthdate,
        gender=data.get('gender'),
        school=data.get('school'),
        inscription_date=inscription_date,
        leave_date=leave_date,
        status=data.get('status', 'actif'),
        notes=data.get('notes')
    )
    db.session.add(student)
    db.session.commit()
    return jsonify(id=student.id), 201

@app.route('/students/<int:id>', methods=['PUT'])
@org_scoped
def update_student(id):
    student = Student.query.filter_by(id=id, organization_id=g.org_id).first_or_404()
    data = request.json
    for key, value in data.items():
        if key in ['birthdate', 'inscription_date', 'leave_date']:
            value = datetime.fromisoformat(value).date() if value else None
        setattr(student, key, value)
    db.session.commit()
    return jsonify(message='Updated')

@app.route('/students/<int:id>/archive', methods=['POST'])
@org_scoped
def archive_student(id):
    student = Student.query.filter_by(id=id, organization_id=g.org_id).first_or_404()
    student.status = 'archivé'
    db.session.commit()
    return jsonify(message='Archived')

@app.route('/students/<int:id>/reactivate', methods=['POST'])
@org_scoped
def reactivate_student(id):
    student = Student.query.filter_by(id=id, organization_id=g.org_id).first_or_404()
    student.status = 'actif'
    db.session.commit()
    return jsonify(message='Reactivated')

@app.route('/students/<int:id>', methods=['GET'])
@org_scoped
def get_student_detail(id):
    student = Student.query.filter_by(id=id, organization_id=g.org_id).first_or_404()
    contacts = ParentContact.query.filter_by(student_id=id).all()
    enrollments = Enrollment.query.filter_by(student_id=id).all()
    transactions = Transaction.query.filter_by(student_id=id).all()
    return jsonify({
        'student': {
            'id': student.id,
            'firstname': student.firstname,
            'lastname': student.lastname,
            'photo_url': student.photo_url,
            'birthdate': serialize_date(student.birthdate),
            'gender': student.gender,
            'school': student.school,
            'inscription_date': serialize_date(student.inscription_date),
            'leave_date': serialize_date(student.leave_date),
            'status': student.status,
            'notes': student.notes,
            'created_at': student.created_at.isoformat(),
            'updated_at': student.updated_at.isoformat()
        },
        'contacts': [{
            'id': c.id,
            'type': c.type,
            'value': c.value,
            'is_principal': c.is_principal,
            'firstname': c.firstname,
            'lastname': c.lastname,
            'relation': c.relation,
            'created_at': c.created_at.isoformat(),
            'updated_at': c.updated_at.isoformat()
        } for c in contacts],
        'enrollments': [{
            'id': e.id,
            'start_date': serialize_date(e.start_date),
            'end_date': serialize_date(e.end_date),
            'amount': float(e.amount),
            'status': e.status,
            'notified_at': e.notified_at.isoformat() if e.notified_at else None,
            'terminated_at': e.terminated_at.isoformat() if e.terminated_at else None,
            'created_at': e.created_at.isoformat(),
            'updated_at': e.updated_at.isoformat()
        } for e in enrollments],
        'transactions': [{
            'id': t.id,
            'date': serialize_date(t.date),
            'type': t.type,
            'amount': float(t.amount),
            'payment_method': t.payment_method,
            'reference': t.reference,
            'category_id': t.category_id,
            'comment': t.comment,
            'created_at': t.created_at.isoformat(),
            'updated_at': t.updated_at.isoformat()
        } for t in transactions]
    })

@app.route('/students/<int:id>', methods=['DELETE'])
@org_scoped
def delete_student(id):
    student = Student.query.filter_by(id=id, organization_id=g.org_id).first_or_404()
    db.session.delete(student)
    db.session.commit()
    return jsonify(message='Deleted')

# Parent Contacts
@app.route('/students/<int:student_id>/contacts', methods=['GET'])
@org_scoped
def get_contacts(student_id):
    Student.query.filter_by(id=student_id, organization_id=g.org_id).first_or_404()
    contacts = ParentContact.query.filter_by(student_id=student_id).all()
    return jsonify([{
        'id': c.id,
        'type': c.type,
        'value': c.value,
        'is_principal': c.is_principal,
        'firstname': c.firstname,
        'lastname': c.lastname,
        'relation': c.relation
    } for c in contacts])

@app.route('/students/<int:student_id>/contacts', methods=['POST'])
@org_scoped
def add_contact(student_id):
    Student.query.filter_by(id=student_id, organization_id=g.org_id).first_or_404()
    data = request.json
    contact = ParentContact(
        student_id=student_id,
        type=data['type'],
        value=data['value'],
        is_principal=data.get('is_principal', False),
        firstname=data.get('firstname'),
        lastname=data.get('lastname'),
        relation=data.get('relation', 'autre')
    )
    db.session.add(contact)
    db.session.commit()
    return jsonify(id=contact.id), 201

@app.route('/students/<int:student_id>/contacts/<int:contact_id>', methods=['PUT'])
@org_scoped
def update_contact(student_id, contact_id):
    contact = ParentContact.query.filter_by(id=contact_id, student_id=student_id).first_or_404()
    data = request.json
    for key, value in data.items():
        setattr(contact, key, value)
    db.session.commit()
    return jsonify(message='Updated')

@app.route('/students/<int:student_id>/contacts/<int:contact_id>', methods=['DELETE'])
@org_scoped
def delete_contact(student_id, contact_id):
    contact = ParentContact.query.filter_by(id=contact_id, student_id=student_id).first_or_404()
    db.session.delete(contact)
    db.session.commit()
    return jsonify(message='Deleted')

# Attendance
@app.route('/attendance', methods=['POST'])
@org_scoped
def record_attendance():
    data = request.json
    date_val = datetime.fromisoformat(data['date']).date()
    for entry in data['entries']:
        student_id = entry['student_id']
        Student.query.filter_by(id=student_id, organization_id=g.org_id).first_or_404()
        att = Attendance.query.filter_by(student_id=student_id, date=date_val).first()
        if not att:
            att = Attendance(
                student_id=student_id,
                organization_id=g.org_id,
                date=date_val
            )
        att.status = entry.get('status', 'absent')
        att.arrival_time = datetime.strptime(entry['arrival_time'], '%H:%M').time() if entry.get('arrival_time') else None
        att.departure_time = datetime.strptime(entry['departure_time'], '%H:%M').time() if entry.get('departure_time') else None
        att.notes = entry.get('notes')
        db.session.add(att)
    db.session.commit()
    return jsonify(message='Recorded')

@app.route('/attendance/report', methods=['GET'])
@org_scoped
def attendance_report():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    period = request.args.get('period', 'daily')  # daily, weekly, monthly
    start = datetime.fromisoformat(start_str).date() if start_str else datetime.now().date() - timedelta(days=30)
    end = datetime.fromisoformat(end_str).date() if end_str else datetime.now().date()

    query = Attendance.query.filter(
        Attendance.organization_id == g.org_id,
        Attendance.date.between(start, end)
    )

    if period == 'daily':
        report = query.with_entities(
            Attendance.date,
            func.count(Attendance.id).label('total'),
            func.sum(func.case([(Attendance.status == 'présent', 1)], else_=0)).label('present'),
            func.sum(func.case([(Attendance.status == 'absent', 1)], else_=0)).label('absent'),
            func.sum(func.case([(Attendance.status == 'justifié', 1)], else_=0)).label('justified')
        ).group_by(Attendance.date).all()
        return jsonify([{
            'date': serialize_date(r.date),
            'total': r.total,
            'present': r.present,
            'absent': r.absent,
            'justified': r.justified
        } for r in report])

    elif period == 'weekly':
        report = query.with_entities(
            func.date_trunc('week', Attendance.date).label('week'),
            func.count(Attendance.id).label('total'),
            func.sum(func.case([(Attendance.status == 'présent', 1)], else_=0)).label('present'),
            func.sum(func.case([(Attendance.status == 'absent', 1)], else_=0)).label('absent'),
            func.sum(func.case([(Attendance.status == 'justifié', 1)], else_=0)).label('justified')
        ).group_by('week').all()
        return jsonify([{
            'week': serialize_date(r.week),
            'total': r.total,
            'present': r.present,
            'absent': r.absent,
            'justified': r.justified
        } for r in report])

    elif period == 'monthly':
        report = query.with_entities(
            extract('year', Attendance.date).label('year'),
            extract('month', Attendance.date).label('month'),
            func.count(Attendance.id).label('total'),
            func.sum(func.case([(Attendance.status == 'présent', 1)], else_=0)).label('present'),
            func.sum(func.case([(Attendance.status == 'absent', 1)], else_=0)).label('absent'),
            func.sum(func.case([(Attendance.status == 'justifié', 1)], else_=0)).label('justified')
        ).group_by('year', 'month').all()
        return jsonify([{
            'year': int(r.year),
            'month': int(r.month),
            'total': r.total,
            'present': r.present,
            'absent': r.absent,
            'justified': r.justified
        } for r in report])

    return jsonify(message='Invalid period'), 400

# Financial Management
@app.route('/transactions', methods=['GET'])
@org_scoped
def get_transactions():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    trans_type = request.args.get('type')
    student_id = request.args.get('student_id')
    start = datetime.fromisoformat(start_str).date() if start_str else None
    end = datetime.fromisoformat(end_str).date() if end_str else None

    query = Transaction.query.filter_by(organization_id=g.org_id)
    if trans_type:
        query = query.filter_by(type=trans_type)
    if student_id:
        query = query.filter_by(student_id=student_id)
    if start and end:
        query = query.filter(Transaction.date.between(start, end))

    transactions = query.all()
    return jsonify([{
        'id': t.id,
        'student_id': t.student_id,
        'date': serialize_date(t.date),
        'type': t.type,
        'amount': float(t.amount),
        'payment_method': t.payment_method,
        'reference': t.reference,
        'category_id': t.category_id,
        'comment': t.comment
    } for t in transactions])

@app.route('/transactions/payment', methods=['POST'])
@org_scoped
def record_payment():
    data = request.json
    student_id = data['student_id']
    amount = data['amount']
    date_val = datetime.fromisoformat(data.get('date', datetime.now().isoformat())).date()
    duration_days = data.get('duration_days', 30)  # Allow customizable duration
    trans = Transaction(
        organization_id=g.org_id,
        student_id=student_id,
        date=date_val,
        type='gain',
        amount=amount,
        payment_method=data['payment_method'],
        reference=data.get('reference'),
        comment=data.get('comment')
    )
    db.session.add(trans)
    
    # Extend or create enrollment
    current_enroll = Enrollment.query.filter_by(student_id=student_id, status='actif').order_by(Enrollment.end_date.desc()).first()
    if current_enroll:
        if current_enroll.end_date:
            current_enroll.end_date += timedelta(days=duration_days)
        current_enroll.status = 'renouvelé'
    else:
        new_enroll = Enrollment(
            student_id=student_id,
            organization_id=g.org_id,
            start_date=date_val,
            end_date=date_val + timedelta(days=duration_days),
            amount=amount,
            status='actif'
        )
        db.session.add(new_enroll)
    
    db.session.commit()
    return jsonify(message='Payment recorded')

@app.route('/transactions/expense', methods=['POST'])
@org_scoped
def record_expense():
    data = request.json
    date_val = datetime.fromisoformat(data.get('date', datetime.now().isoformat())).date()
    trans = Transaction(
        organization_id=g.org_id,
        date=date_val,
        type='dépense',
        amount=-abs(data['amount']),  # Ensure negative
        payment_method=data['payment_method'],
        category_id=data['category_id'],
        reference=data.get('reference'),
        comment=data.get('comment')
    )
    db.session.add(trans)
    db.session.commit()
    return jsonify(message='Expense recorded')

# Dashboard
@app.route('/dashboard', methods=['GET'])
@org_scoped
def dashboard():
    # Current balance
    balance = db.session.query(func.sum(Transaction.amount)).filter_by(organization_id=g.org_id).scalar() or 0.0

    # Upcoming payments (enrollments expiring in next 7 days)
    today = datetime.now().date()
    upcoming = Enrollment.query.filter(
        Enrollment.organization_id == g.org_id,
        Enrollment.end_date <= today + timedelta(days=7),
        Enrollment.end_date >= today,
        Enrollment.status == 'actif'
    ).count()

    # Active students
    active_students = Student.query.filter_by(organization_id=g.org_id, status='actif').count()

    # Monthly expenses by category (current month)
    current_month = today.month
    current_year = today.year
    expenses_by_cat = db.session.query(
        TransactionCategory.label,
        func.sum(Transaction.amount).label('total')
    ).join(TransactionCategory, Transaction.category_id == TransactionCategory.id).filter(
        Transaction.organization_id == g.org_id,
        Transaction.type == 'dépense',
        extract('month', Transaction.date) == current_month,
        extract('year', Transaction.date) == current_year
    ).group_by(TransactionCategory.label).all()

    return jsonify({
        'balance': float(balance),
        'upcoming_payments': upcoming,
        'active_students': active_students,
        'monthly_expenses': {cat: float(total) for cat, total in expenses_by_cat}
    })

# Enrollments
@app.route('/enrollments', methods=['POST'])
@org_scoped
def add_enrollment():
    data = request.json
    student_id = data['student_id']
    Student.query.filter_by(id=student_id, organization_id=g.org_id).first_or_404()
    start_date = datetime.fromisoformat(data['start_date']).date()
    end_date = datetime.fromisoformat(data['end_date']).date() if data.get('end_date') else None
    enroll = Enrollment(
        student_id=student_id,
        organization_id=g.org_id,
        start_date=start_date,
        end_date=end_date,
        amount=data['amount'],
        status=data.get('status', 'actif')
    )
    db.session.add(enroll)
    db.session.commit()
    return jsonify(id=enroll.id), 201

@app.route('/enrollments/check', methods=['POST'])
@org_scoped
def check_expirations():
    today = datetime.now().date()
    thresholds = [0, 1, 3, 7]  # Days before expiration to notify
    expiring = Enrollment.query.filter(
        Enrollment.organization_id == g.org_id,
        Enrollment.status == 'actif',
        Enrollment.end_date.isnot(None),
        Enrollment.end_date - today <= max(thresholds),
        db.or_(Enrollment.notified_at.is_(None), Enrollment.notified_at < today)
    ).all()
    notified = []
    for e in expiring:
        days_left = (e.end_date - today).days
        if days_left in thresholds:
            e.notified_at = datetime.now()
            # Integrate email sending here (placeholder)
            # For example: send_email(e.student.email, f"Inscription expire dans {days_left} jours")
            logging.info(f'Notification for enrollment {e.id} - {days_left} days left')
            notified.append(e.id)
    db.session.commit()
    return jsonify(notified=notified)

@app.route('/enrollments/<int:id>/renew', methods=['POST'])
@org_scoped
def renew_enrollment(id):
    data = request.json
    duration_days = data.get('duration_days', 30)
    enroll = Enrollment.query.filter_by(id=id, organization_id=g.org_id).first_or_404()
    enroll.status = 'renouvelé'
    new_start = enroll.end_date + timedelta(days=1) if enroll.end_date else datetime.now().date()
    new_enroll = Enrollment(
        student_id=enroll.student_id,
        organization_id=g.org_id,
        start_date=new_start,
        end_date=new_start + timedelta(days=duration_days),
        amount=data.get('amount', enroll.amount),
        status='actif'
    )
    db.session.add(new_enroll)
    db.session.commit()
    return jsonify(new_id=new_enroll.id, message='Renewed')

@app.route('/enrollments/<int:id>/terminate', methods=['POST'])
@org_scoped
def terminate_enrollment(id):
    enroll = Enrollment.query.filter_by(id=id, organization_id=g.org_id).first_or_404()
    enroll.status = 'résilié'
    enroll.terminated_at = datetime.now()
    db.session.commit()
    return jsonify(message='Terminated')

# Reports
@app.route('/reports/monthly', methods=['GET'])
@org_scoped
def monthly_report():
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    # Total gains
    gains = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.organization_id == g.org_id,
        Transaction.type == 'gain',
        extract('year', Transaction.date) == year,
        extract('month', Transaction.date) == month
    ).scalar() or 0.0
    
    # Total expenses by category
    expenses_by_cat = db.session.query(
        TransactionCategory.label,
        func.sum(Transaction.amount).label('total')
    ).join(TransactionCategory, Transaction.category_id == TransactionCategory.id).filter(
        Transaction.organization_id == g.org_id,
        Transaction.type == 'dépense',
        extract('year', Transaction.date) == year,
        extract('month', Transaction.date) == month
    ).group_by(TransactionCategory.label).all()
    total_expenses = sum(float(t) for _, t in expenses_by_cat)
    
    # Profit/loss
    profit_loss = gains + total_expenses  # Since expenses are negative
    
    # Average active students (count distinct students with active enrollment in the month)
    avg_students = db.session.query(func.count(func.distinct(Enrollment.student_id))).filter(
        Enrollment.organization_id == g.org_id,
        Enrollment.status.in_(['actif', 'renouvelé']),
        Enrollment.start_date <= date(year, month, 1) + timedelta(days=31),
        db.or_(Enrollment.end_date >= date(year, month, 1), Enrollment.end_date.is_(None))
    ).scalar() or 0
    
    return jsonify({
        'gains': float(gains),
        'expenses': {cat: float(total) for cat, total in expenses_by_cat},
        'total_expenses': float(total_expenses),
        'profit_loss': float(profit_loss),
        'avg_active_students': avg_students
    })

@app.route('/reports/annual', methods=['GET'])
@org_scoped
def annual_report():
    year = int(request.args.get('year', datetime.now().year))
    
    # Similar to monthly, but group by year
    gains = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.organization_id == g.org_id,
        Transaction.type == 'gain',
        extract('year', Transaction.date) == year
    ).scalar() or 0.0
    
    expenses_by_cat = db.session.query(
        TransactionCategory.label,
        func.sum(Transaction.amount).label('total')
    ).join(TransactionCategory, Transaction.category_id == TransactionCategory.id).filter(
        Transaction.organization_id == g.org_id,
        Transaction.type == 'dépense',
        extract('year', Transaction.date) == year
    ).group_by(TransactionCategory.label).all()
    total_expenses = sum(float(t) for _, t in expenses_by_cat)
    
    profit_loss = gains + total_expenses
    
    # Average monthly active students
    monthly_avgs = []
    for m in range(1, 13):
        avg = db.session.query(func.count(func.distinct(Enrollment.student_id))).filter(
            Enrollment.organization_id == g.org_id,
            Enrollment.status.in_(['actif', 'renouvelé']),
            Enrollment.start_date <= date(year, m, 1) + timedelta(days=31),
            db.or_(Enrollment.end_date >= date(year, m, 1), Enrollment.end_date.is_(None))
        ).scalar() or 0
        monthly_avgs.append(avg)
    avg_students = sum(monthly_avgs) / 12 if monthly_avgs else 0
    
    return jsonify({
        'gains': float(gains),
        'expenses': {cat: float(total) for cat, total in expenses_by_cat},
        'total_expenses': float(total_expenses),
        'profit_loss': float(profit_loss),
        'avg_active_students': avg_students
    })

# Categories
@app.route('/categories', methods=['GET'])
@org_scoped
def get_categories():
    cats = TransactionCategory.query.filter_by(organization_id=g.org_id).all()
    return jsonify([{
        'id': c.id,
        'label': c.label,
        'is_system': c.is_system
    } for c in cats])

@app.route('/categories', methods=['POST'])
@org_scoped
def add_category():
    data = request.json
    cat = TransactionCategory(
        organization_id=g.org_id,
        label=data['label'],
        is_system=data.get('is_system', False)
    )
    db.session.add(cat)
    db.session.commit()
    return jsonify(id=cat.id), 201

@app.route('/categories/<int:id>', methods=['PUT'])
@org_scoped
def update_category(id):
    cat = TransactionCategory.query.filter_by(id=id, organization_id=g.org_id).first_or_404()
    data = request.json
    cat.label = data.get('label', cat.label)
    db.session.commit()
    return jsonify(message='Updated')

@app.route('/categories/<int:id>', methods=['DELETE'])
@org_scoped
def delete_category(id):
    cat = TransactionCategory.query.filter_by(id=id, organization_id=g.org_id).first_or_404()
    if cat.is_system:
        return jsonify(message='Cannot delete system category'), 403
    db.session.delete(cat)
    db.session.commit()
    return jsonify(message='Deleted')

# Settings / Organization Profile
@app.route('/organization', methods=['GET'])
@org_scoped
def get_organization():
    org = Organization.query.get(g.org_id)
    return jsonify({
        'id': org.id,
        'company_name': org.company_name,
        'manager_name': org.manager_name,
        'manager_lastname': org.manager_lastname,
        'email': org.email,
        'birthdate': serialize_date(org.birthdate),
        'logo_url': org.logo_url,
        'address': org.address
    })

@app.route('/organization', methods=['PUT'])
@org_scoped
def update_organization():
    org = Organization.query.get(g.org_id)
    data = request.json
    for key, value in data.items():
        if key == 'birthdate':
            value = datetime.fromisoformat(value).date() if value else None
        if key != 'password_hash' and key != 'email':  # Prevent changing email/password here
            setattr(org, key, value)
    db.session.commit()
    return jsonify(message='Updated')

@app.route('/organization/change-password', methods=['POST'])
@org_scoped
def change_password():
    data = request.json
    org = Organization.query.get(g.org_id)
    if check_password_hash(org.password_hash, data['old_password']):
        org.password_hash = generate_password_hash(data['new_password'])
        db.session.commit()
        return jsonify(message='Password changed')
    return jsonify(message='Invalid old password'), 401

if __name__ == '__main__':
    app.run(debug=True)
