import os
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
import smtplib
from pathlib import Path

from flask import current_app
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from .extensions import db
from .models import (
    Department,
    Notification,
    SLASetting,
    Ticket,
    TicketActivityLog,
    User,
    ROLE_ADMIN,
    ROLE_APPROVER,
    ROLE_REQUESTER,
    ROLE_STAFF,
    STATUS_APPROVED,
    STATUS_CLOSED,
    STATUS_OPEN,
    STATUS_REJECTED,
    STATUS_RESOLVED,
)

CATEGORY_MAP = {
    "IT Department": [
        "Computer issues",
        "Printer issues",
        "Network/Wi-Fi problems",
        "Software installation",
        "Smart Board issues",
        "Projector issues",
        "New equipment requests",
    ],
    "Maintenance Department": [
        "Electrical problems",
        "Plumbing issues",
        "Furniture repairs",
        "Classroom maintenance",
        "Building maintenance",
    ],
    "Food/Canteen Department": [
        "Food quality concerns",
        "Kitchen equipment issues",
        "Dining hall maintenance",
    ],
    "Academic Department": [
        "Timetable issues",
        "Examination-related queries",
        "Student academic concerns",
        "Teaching resource requests",
    ],
    "Administration Department": [
        "Approval/document support",
        "General administration",
        "Procurement request",
    ],
    "Hostel Department": [
        "Room maintenance",
        "Hostel safety concern",
        "Housekeeping issue",
    ],
    "Transport Department": [
        "Vehicle request",
        "Route issue",
        "Transport maintenance",
    ],
}

DEFAULT_SLA = {"Low": 72, "Medium": 48, "High": 24, "Critical": 8}
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "doc", "docx", "xls", "xlsx", "txt"}


def seed_defaults():
    departments = [
        ("IT Department", "IT"),
        ("Maintenance Department", "MNT"),
        ("Food/Canteen Department", "FOD"),
        ("Academic Department", "ACD"),
        ("Administration Department", "ADM"),
        ("Hostel Department", "HST"),
        ("Transport Department", "TRN"),
    ]
    for name, code in departments:
        dept = Department.query.filter_by(code=code).first()
        if not dept:
            db.session.add(Department(name=name, code=code, description=f"{name} service desk"))
    db.session.commit()

    admin = User.query.filter_by(email=current_app.config["DEFAULT_ADMIN_EMAIL"]).first()
    if not admin:
        admin = User(
            full_name="Super Administrator",
            email=current_app.config["DEFAULT_ADMIN_EMAIL"],
            role=ROLE_ADMIN,
            is_active_user=True,
        )
        admin.set_password(current_app.config["DEFAULT_ADMIN_PASSWORD"])
        db.session.add(admin)
        db.session.commit()

    for dept in Department.query.all():
        for priority, hours in DEFAULT_SLA.items():
            existing = SLASetting.query.filter_by(department_id=dept.id, priority=priority).first()
            if not existing:
                db.session.add(
                    SLASetting(
                        department_id=dept.id,
                        priority=priority,
                        resolution_hours=hours,
                        escalation_hours=max(1, int(hours * 0.75)),
                    )
                )
    db.session.commit()


def generate_ticket_number():
    count = Ticket.query.count() + 1
    return f"TSK-{datetime.utcnow().strftime('%Y%m%d')}-{count:04d}"


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_attachments(files, ticket_id, user_id):
    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    upload_root.mkdir(parents=True, exist_ok=True)
    saved = []
    from .models import TicketAttachment

    for file in files:
        if not file or not file.filename:
            continue
        if not allowed_file(file.filename):
            continue
        original = secure_filename(file.filename)
        unique_name = f"{ticket_id}_{uuid.uuid4().hex}_{original}"
        file_path = upload_root / unique_name
        file.save(file_path)
        attachment = TicketAttachment(
            ticket_id=ticket_id,
            uploader_id=user_id,
            original_filename=original,
            stored_filename=unique_name,
            file_path=str(file_path),
        )
        db.session.add(attachment)
        saved.append(attachment)
    db.session.commit()
    return saved


def create_activity(ticket, actor, action, from_status=None, to_status=None, note=None):
    activity = TicketActivityLog(
        ticket_id=ticket.id,
        actor_id=actor.id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        note=note,
    )
    db.session.add(activity)
    db.session.commit()
    return activity


def create_notification(user, ticket, message, send_mail=False):
    notification = Notification(user_id=user.id, ticket_id=ticket.id if ticket else None, message=message)
    db.session.add(notification)
    db.session.commit()
    if send_mail:
        send_email(user.email, f"Ticket Update - {ticket.ticket_number if ticket else 'System'}", message)
    return notification


def notify_users(users, ticket, message):
    seen = set()
    for user in users:
        if not user or user.id in seen:
            continue
        create_notification(user, ticket, message, send_mail=current_app.config["MAIL_ENABLED"])
        seen.add(user.id)


def send_email(recipient, subject, body):
    if not current_app.config["MAIL_ENABLED"] or not recipient:
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = current_app.config["MAIL_FROM"]
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP(current_app.config["MAIL_HOST"], current_app.config["MAIL_PORT"]) as server:
        if current_app.config["MAIL_USE_TLS"]:
            server.starttls()
        if current_app.config["MAIL_USERNAME"]:
            server.login(current_app.config["MAIL_USERNAME"], current_app.config["MAIL_PASSWORD"])
        server.send_message(msg)


def calculate_due_date(department_id, priority):
    sla = SLASetting.query.filter_by(department_id=department_id, priority=priority).first()
    hours = sla.resolution_hours if sla else DEFAULT_SLA.get(priority, 48)
    return datetime.utcnow() + timedelta(hours=hours)


def approvers_for_department(department_id):
    return User.query.filter(
        User.department_id == department_id,
        User.role.in_([ROLE_APPROVER, ROLE_ADMIN]),
        User.is_active_user.is_(True),
    ).all()


def staff_for_department(department_id):
    return User.query.filter_by(
        department_id=department_id,
        role=ROLE_STAFF,
        is_active_user=True,
    ).all()


def ticket_scope_query(user):
    query = Ticket.query
    if user.role == ROLE_ADMIN:
        return query
    if user.role == ROLE_REQUESTER:
        return query.filter(Ticket.requester_id == user.id)
    if user.role == ROLE_APPROVER:
        return query.filter(Ticket.department_id == user.department_id)
    if user.role == ROLE_STAFF:
        return query.filter(
            or_(Ticket.assigned_to_id == user.id, Ticket.department_id == user.department_id)
        )
    return query.filter(Ticket.requester_id == user.id)


def searchable_ticket_query(query, term):
    if not term:
        return query
    like = f"%{term}%"
    return query.filter(
        or_(
            Ticket.ticket_number.ilike(like),
            Ticket.title.ilike(like),
            Ticket.description.ilike(like),
            Ticket.category.ilike(like),
        )
    )


def dashboard_summary(user):
    base = ticket_scope_query(user)
    total = base.count()
    open_count = base.filter(Ticket.status.in_(["Open", "Under Review", "Approved", "In Progress", "Waiting for Information"])).count()
    resolved_count = base.filter(Ticket.status == STATUS_RESOLVED).count()
    closed_count = base.filter(Ticket.status == STATUS_CLOSED).count()
    overdue_count = base.filter(Ticket.due_at.isnot(None), Ticket.due_at < datetime.utcnow(), Ticket.status.notin_([STATUS_RESOLVED, STATUS_CLOSED, STATUS_REJECTED])).count()
    resolved_rows = Ticket.query.filter(Ticket.resolved_at.isnot(None)).all()
    avg_hours = 0
    if resolved_rows:
        avg_hours = round(
            sum([(row.resolved_at - row.created_at).total_seconds() / 3600 for row in resolved_rows]) / len(resolved_rows),
            2,
        )
    return {
        "total": total,
        "open": open_count,
        "resolved": resolved_count,
        "closed": closed_count,
        "overdue": overdue_count,
        "avg_resolution_hours": avg_hours,
    }


def escalation_candidates():
    candidates = []
    now = datetime.utcnow()
    open_rows = Ticket.query.filter(
        Ticket.status.notin_([STATUS_RESOLVED, STATUS_CLOSED, STATUS_REJECTED])
    ).all()
    for ticket in open_rows:
        sla = SLASetting.query.filter_by(
            department_id=ticket.department_id, priority=ticket.priority
        ).first()
        if not sla:
            continue
        if ticket.created_at + timedelta(hours=sla.escalation_hours) < now:
            candidates.append(ticket)
    return candidates
