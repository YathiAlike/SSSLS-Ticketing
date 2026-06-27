from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from ..decorators import role_required
from ..extensions import db
from ..models import Department, PRIORITIES, ROLE_ADMIN, ROLES, SLASetting, Ticket, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def users():
    departments = Department.query.order_by(Department.name.asc()).all()
    if request.method == "POST":
        user_id = request.form.get("user_id", type=int)
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "requester")
        department_id = request.form.get("department_id", type=int)
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        is_active_user = request.form.get("is_active_user") == "on"

        if user_id:
            user = User.query.get_or_404(user_id)
        else:
            user = User()
            db.session.add(user)

        if not full_name or not email or role not in ROLES:
            flash("Name, email and role are required.", "danger")
            return redirect(url_for("admin.users"))

        user.full_name = full_name
        user.email = email
        user.role = role
        user.department_id = department_id or None
        user.phone = phone
        user.is_active_user = is_active_user or not user_id
        if password:
            user.set_password(password)
        elif not user_id:
            user.set_password("ChangeMe@123")

        db.session.commit()
        flash("User saved successfully.", "success")
        return redirect(url_for("admin.users"))

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users, departments=departments, roles=ROLES)


@admin_bp.route("/departments", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def departments():
    if request.method == "POST":
        department_id = request.form.get("department_id", type=int)
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()
        email = request.form.get("email", "").strip()
        description = request.form.get("description", "").strip()
        is_active = request.form.get("is_active") == "on"

        if department_id:
            department = Department.query.get_or_404(department_id)
        else:
            department = Department()
            db.session.add(department)

        department.name = name
        department.code = code
        department.email = email
        department.description = description
        department.is_active = is_active or not department_id
        db.session.commit()
        flash("Department saved successfully.", "success")
        return redirect(url_for("admin.departments"))

    departments = Department.query.order_by(Department.name.asc()).all()
    return render_template("admin/departments.html", departments=departments)


@admin_bp.route("/sla", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def sla():
    departments = Department.query.order_by(Department.name.asc()).all()
    if request.method == "POST":
        for department in departments:
            for priority in PRIORITIES:
                resolution_hours = request.form.get(f"resolution_{department.id}_{priority}", type=int)
                escalation_hours = request.form.get(f"escalation_{department.id}_{priority}", type=int)
                record = SLASetting.query.filter_by(department_id=department.id, priority=priority).first()
                if not record:
                    record = SLASetting(department_id=department.id, priority=priority)
                    db.session.add(record)
                record.resolution_hours = resolution_hours or 48
                record.escalation_hours = escalation_hours or 24
        db.session.commit()
        flash("SLA settings updated.", "success")
        return redirect(url_for("admin.sla"))

    settings = {(item.department_id, item.priority): item for item in SLASetting.query.all()}
    return render_template("admin/sla.html", departments=departments, priorities=PRIORITIES, settings=settings)


@admin_bp.route("/reports")
@login_required
@role_required(ROLE_ADMIN)
def reports():
    dept_breakdown = (
        db.session.query(Department.name, func.count(Ticket.id))
        .outerjoin(Ticket, Ticket.department_id == Department.id)
        .group_by(Department.name)
        .order_by(func.count(Ticket.id).desc())
        .all()
    )
    status_breakdown = (
        db.session.query(Ticket.status, func.count(Ticket.id))
        .group_by(Ticket.status)
        .order_by(func.count(Ticket.id).desc())
        .all()
    )
    priority_breakdown = (
        db.session.query(Ticket.priority, func.count(Ticket.id))
        .group_by(Ticket.priority)
        .order_by(func.count(Ticket.id).desc())
        .all()
    )
    resolution_rows = Ticket.query.filter(Ticket.resolved_at.isnot(None)).all()
    avg_resolution = round(
        sum([(row.resolved_at - row.created_at).total_seconds() / 3600 for row in resolution_rows]) / len(resolution_rows),
        2,
    ) if resolution_rows else 0
    overdue = [ticket for ticket in Ticket.query.all() if ticket.is_overdue]
    return render_template(
        "admin/reports.html",
        dept_breakdown=dept_breakdown,
        status_breakdown=status_breakdown,
        priority_breakdown=priority_breakdown,
        avg_resolution=avg_resolution,
        overdue=overdue,
    )
