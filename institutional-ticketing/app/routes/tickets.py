from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from ..decorators import department_match_or_admin
from ..extensions import db
from ..models import (
    Department,
    PRIORITIES,
    ROLE_ADMIN,
    ROLE_APPROVER,
    ROLE_REQUESTER,
    ROLE_STAFF,
    STATUS_APPROVED,
    STATUS_CLOSED,
    STATUS_IN_PROGRESS,
    STATUS_OPEN,
    STATUS_REJECTED,
    STATUS_RESOLVED,
    STATUS_UNDER_REVIEW,
    STATUS_WAITING,
    Ticket,
    TicketAttachment,
    TicketComment,
)
from ..services import (
    CATEGORY_MAP,
    approvers_for_department,
    calculate_due_date,
    create_activity,
    generate_ticket_number,
    notify_users,
    save_attachments,
    searchable_ticket_query,
    staff_for_department,
    ticket_scope_query,
)

tickets_bp = Blueprint("tickets", __name__, url_prefix="/tickets")


@tickets_bp.route("/")
@login_required
def list_tickets():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    priority = request.args.get("priority", "").strip()
    department_id = request.args.get("department_id", "").strip()

    query = ticket_scope_query(current_user).order_by(Ticket.created_at.desc())
    query = searchable_ticket_query(query, search)
    if status:
        query = query.filter(Ticket.status == status)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if department_id and current_user.role == ROLE_ADMIN:
        query = query.filter(Ticket.department_id == int(department_id))

    tickets = query.all()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name.asc()).all()
    return render_template(
        "tickets/list.html",
        tickets=tickets,
        departments=departments,
        priorities=PRIORITIES,
    )


@tickets_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_ticket():
    departments = Department.query.filter_by(is_active=True).order_by(Department.name.asc()).all()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        department_id = request.form.get("department_id", type=int)
        category = request.form.get("category", "").strip()
        custom_category = request.form.get("custom_category", "").strip()
        priority = request.form.get("priority", "Medium").strip()
        location = request.form.get("location", "").strip()

        if not title or not description or not department_id:
            flash("Title, description and department are required.", "danger")
            return render_template(
                "tickets/create.html",
                departments=departments,
                priorities=PRIORITIES,
                category_map=CATEGORY_MAP,
            )

        if custom_category:
            category = custom_category
        if not category:
            category = "General Request"

        ticket = Ticket(
            ticket_number=generate_ticket_number(),
            title=title,
            description=description,
            department_id=department_id,
            category=category,
            priority=priority,
            status=STATUS_OPEN,
            location=location,
            requester_id=current_user.id,
            due_at=calculate_due_date(department_id, priority),
        )
        db.session.add(ticket)
        db.session.commit()

        save_attachments(request.files.getlist("attachments"), ticket.id, current_user.id)
        create_activity(ticket, current_user, "Ticket created", None, STATUS_OPEN, description[:250])

        approvers = approvers_for_department(department_id)
        recipients = approvers + [current_user]
        notify_users(
            recipients,
            ticket,
            f"Ticket {ticket.ticket_number} created and routed to {ticket.department.name}.",
        )
        flash(f"Ticket {ticket.ticket_number} has been created.", "success")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    return render_template(
        "tickets/create.html",
        departments=departments,
        priorities=PRIORITIES,
        category_map=CATEGORY_MAP,
    )


@tickets_bp.route("/<int:ticket_id>")
@login_required
def detail(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if not department_match_or_admin(ticket):
        abort(403)

    staff_members = staff_for_department(ticket.department_id)
    return render_template(
        "tickets/detail.html",
        ticket=ticket,
        staff_members=staff_members,
        statuses=[STATUS_OPEN, STATUS_UNDER_REVIEW, STATUS_APPROVED, STATUS_IN_PROGRESS, STATUS_WAITING, STATUS_RESOLVED, STATUS_CLOSED, STATUS_REJECTED],
    )


@tickets_bp.route("/<int:ticket_id>/comment", methods=["POST"])
@login_required
def add_comment(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if not department_match_or_admin(ticket):
        abort(403)

    comment_text = request.form.get("comment", "").strip()
    is_internal = request.form.get("is_internal") == "on"
    if not comment_text:
        flash("Comment cannot be empty.", "warning")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    if is_internal and current_user.role not in [ROLE_APPROVER, ROLE_STAFF, ROLE_ADMIN]:
        is_internal = False

    comment = TicketComment(ticket_id=ticket.id, user_id=current_user.id, comment=comment_text, is_internal=is_internal)
    db.session.add(comment)
    db.session.commit()
    create_activity(ticket, current_user, "Comment added", ticket.status, ticket.status, comment_text[:250])

    recipients = [ticket.requester]
    if ticket.approver:
        recipients.append(ticket.approver)
    if ticket.assignee:
        recipients.append(ticket.assignee)
    notify_users(recipients, ticket, f"New comment added on ticket {ticket.ticket_number}.")
    flash("Comment added.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.route("/<int:ticket_id>/action", methods=["POST"])
@login_required
def workflow_action(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if not department_match_or_admin(ticket):
        abort(403)

    action = request.form.get("action", "").strip()
    note = request.form.get("note", "").strip()
    previous_status = ticket.status
    recipients = [ticket.requester]

    if action == "review":
        if current_user.role not in [ROLE_APPROVER, ROLE_ADMIN]:
            abort(403)
        ticket.status = STATUS_UNDER_REVIEW

    elif action == "approve":
        if current_user.role not in [ROLE_APPROVER, ROLE_ADMIN]:
            abort(403)
        ticket.status = STATUS_APPROVED
        ticket.approver_id = current_user.id
        ticket.approved_at = datetime.utcnow()

    elif action == "reject":
        if current_user.role not in [ROLE_APPROVER, ROLE_ADMIN]:
            abort(403)
        ticket.status = STATUS_REJECTED
        ticket.approver_id = current_user.id
        ticket.rejection_reason = note or "Request rejected"

    elif action == "assign":
        if current_user.role not in [ROLE_APPROVER, ROLE_ADMIN]:
            abort(403)
        assignee_id = request.form.get("assignee_id", type=int)
        if not assignee_id:
            flash("Please select a staff member.", "warning")
            return redirect(url_for("tickets.detail", ticket_id=ticket.id))
        ticket.assigned_to_id = assignee_id
        ticket.approver_id = current_user.id
        ticket.status = STATUS_IN_PROGRESS if previous_status in [STATUS_APPROVED, STATUS_UNDER_REVIEW, STATUS_OPEN] else previous_status

    elif action == "progress":
        if current_user.role not in [ROLE_STAFF, ROLE_APPROVER, ROLE_ADMIN]:
            abort(403)
        ticket.status = STATUS_IN_PROGRESS

    elif action == "wait_info":
        if current_user.role not in [ROLE_STAFF, ROLE_APPROVER, ROLE_ADMIN]:
            abort(403)
        ticket.status = STATUS_WAITING

    elif action == "resolve":
        if current_user.role not in [ROLE_STAFF, ROLE_APPROVER, ROLE_ADMIN]:
            abort(403)
        ticket.status = STATUS_RESOLVED
        ticket.resolved_at = datetime.utcnow()

    elif action == "close":
        if current_user.id != ticket.requester_id and current_user.role not in [ROLE_APPROVER, ROLE_ADMIN]:
            abort(403)
        ticket.status = STATUS_CLOSED
        ticket.closed_at = datetime.utcnow()
        if current_user.id == ticket.requester_id:
            ticket.satisfaction_rating = request.form.get("satisfaction_rating", type=int)
            ticket.satisfaction_comment = request.form.get("satisfaction_comment", "").strip()

    elif action == "reopen":
        if current_user.id != ticket.requester_id and current_user.role not in [ROLE_APPROVER, ROLE_ADMIN]:
            abort(403)
        ticket.status = STATUS_OPEN
        ticket.closed_at = None
        ticket.resolved_at = None
    else:
        flash("Unknown action.", "danger")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    db.session.commit()
    create_activity(ticket, current_user, action.replace("_", " ").title(), previous_status, ticket.status, note)

    if ticket.approver:
        recipients.append(ticket.approver)
    if ticket.assignee:
        recipients.append(ticket.assignee)
    notify_users(recipients, ticket, f"Ticket {ticket.ticket_number} updated: {previous_status} → {ticket.status}.")

    flash(f"Ticket updated to {ticket.status}.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.route("/attachments/<int:attachment_id>")
@login_required
def download_attachment(attachment_id):
    attachment = TicketAttachment.query.get_or_404(attachment_id)
    ticket = attachment.ticket
    if not department_match_or_admin(ticket):
        abort(403)
    path = Path(attachment.file_path)
    if not path.exists():
        abort(404)
    return send_file(path, as_attachment=True, download_name=attachment.original_filename)
