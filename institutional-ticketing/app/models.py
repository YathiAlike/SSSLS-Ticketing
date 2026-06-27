from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

ROLE_REQUESTER = "requester"
ROLE_APPROVER = "approver"
ROLE_STAFF = "staff"
ROLE_ADMIN = "admin"
ROLES = [ROLE_REQUESTER, ROLE_APPROVER, ROLE_STAFF, ROLE_ADMIN]

STATUS_OPEN = "Open"
STATUS_UNDER_REVIEW = "Under Review"
STATUS_APPROVED = "Approved"
STATUS_IN_PROGRESS = "In Progress"
STATUS_WAITING = "Waiting for Information"
STATUS_RESOLVED = "Resolved"
STATUS_CLOSED = "Closed"
STATUS_REJECTED = "Rejected"
STATUSES = [
    STATUS_OPEN,
    STATUS_UNDER_REVIEW,
    STATUS_APPROVED,
    STATUS_IN_PROGRESS,
    STATUS_WAITING,
    STATUS_RESOLVED,
    STATUS_CLOSED,
    STATUS_REJECTED,
]

PRIORITIES = ["Low", "Medium", "High", "Critical"]


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Department(TimestampMixin, db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text)
    email = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    users = db.relationship("User", back_populates="department", lazy=True)
    tickets = db.relationship("Ticket", back_populates="department", lazy=True)
    sla_settings = db.relationship("SLASetting", back_populates="department", lazy=True)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default=ROLE_REQUESTER)
    phone = db.Column(db.String(30))
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)

    department = db.relationship("Department", back_populates="users")
    requested_tickets = db.relationship(
        "Ticket", back_populates="requester", lazy=True, foreign_keys="Ticket.requester_id"
    )
    approved_tickets = db.relationship(
        "Ticket", back_populates="approver", lazy=True, foreign_keys="Ticket.approver_id"
    )
    assigned_tickets = db.relationship(
        "Ticket", back_populates="assignee", lazy=True, foreign_keys="Ticket.assigned_to_id"
    )
    comments = db.relationship("TicketComment", back_populates="user", lazy=True)
    activities = db.relationship("TicketActivityLog", back_populates="actor", lazy=True)
    notifications = db.relationship("Notification", back_populates="user", lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.is_active_user

    def get_role_label(self):
        return self.role.replace("_", " ").title()


@login_manager.user_loader

def load_user(user_id):
    return User.query.get(int(user_id))


class Ticket(TimestampMixin, db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(120), nullable=False)
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    status = db.Column(db.String(30), nullable=False, default=STATUS_OPEN)
    location = db.Column(db.String(255))
    due_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    satisfaction_rating = db.Column(db.Integer)
    satisfaction_comment = db.Column(db.Text)

    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    department = db.relationship("Department", back_populates="tickets")
    requester = db.relationship("User", back_populates="requested_tickets", foreign_keys=[requester_id])
    approver = db.relationship("User", back_populates="approved_tickets", foreign_keys=[approver_id])
    assignee = db.relationship("User", back_populates="assigned_tickets", foreign_keys=[assigned_to_id])
    comments = db.relationship(
        "TicketComment", back_populates="ticket", lazy=True, cascade="all, delete-orphan"
    )
    attachments = db.relationship(
        "TicketAttachment", back_populates="ticket", lazy=True, cascade="all, delete-orphan"
    )
    activities = db.relationship(
        "TicketActivityLog", back_populates="ticket", lazy=True, cascade="all, delete-orphan"
    )
    notifications = db.relationship(
        "Notification", back_populates="ticket", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def is_overdue(self):
        if not self.due_at or self.status in [STATUS_RESOLVED, STATUS_CLOSED, STATUS_REJECTED]:
            return False
        return datetime.utcnow() > self.due_at

    @property
    def resolution_hours(self):
        if not self.resolved_at:
            return None
        seconds = (self.resolved_at - self.created_at).total_seconds()
        return round(seconds / 3600, 2)


class TicketComment(db.Model):
    __tablename__ = "ticket_comments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship("Ticket", back_populates="comments")
    user = db.relationship("User", back_populates="comments")


class TicketAttachment(db.Model):
    __tablename__ = "ticket_attachments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship("Ticket", back_populates="attachments")


class TicketActivityLog(db.Model):
    __tablename__ = "ticket_activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(120), nullable=False)
    from_status = db.Column(db.String(30))
    to_status = db.Column(db.String(30))
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship("Ticket", back_populates="activities")
    actor = db.relationship("User", back_populates="activities")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=True)
    message = db.Column(db.String(500), nullable=False)
    channel = db.Column(db.String(30), default="in_app", nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="notifications")
    ticket = db.relationship("Ticket", back_populates="notifications")


class SLASetting(TimestampMixin, db.Model):
    __tablename__ = "sla_settings"

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    resolution_hours = db.Column(db.Integer, nullable=False)
    escalation_hours = db.Column(db.Integer, nullable=False)

    department = db.relationship("Department", back_populates="sla_settings")
    __table_args__ = (db.UniqueConstraint("department_id", "priority", name="uq_sla_department_priority"),)
