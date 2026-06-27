from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..models import Department, Notification, Ticket
from ..services import dashboard_summary, ticket_scope_query

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def dashboard():
    summary = dashboard_summary(current_user)
    recent_tickets = ticket_scope_query(current_user).order_by(Ticket.created_at.desc()).limit(8).all()
    dept_stats = (
        db.session.query(Department.name, func.count(Ticket.id))
        .outerjoin(Ticket, Ticket.department_id == Department.id)
        .group_by(Department.name)
        .order_by(Department.name.asc())
        .all()
    )
    return render_template(
        "dashboard/index.html",
        summary=summary,
        recent_tickets=recent_tickets,
        dept_stats=dept_stats,
    )


@main_bp.route("/notifications/<int:notification_id>/read")
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    notification.is_read = True
    db.session.commit()
    flash("Notification marked as read.", "success")
    if notification.ticket_id:
        return redirect(url_for("tickets.detail", ticket_id=notification.ticket_id))
    return redirect(url_for("main.dashboard"))
