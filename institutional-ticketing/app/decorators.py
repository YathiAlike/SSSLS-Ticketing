from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user

from .models import ROLE_ADMIN


def role_required(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles and current_user.role != ROLE_ADMIN:
                flash("You do not have permission to access this resource.", "danger")
                return redirect(url_for("main.dashboard"))
            return func(*args, **kwargs)

        return wrapper

    return decorator


def department_match_or_admin(ticket):
    if current_user.role == ROLE_ADMIN:
        return True
    if current_user.role in ["approver", "staff"]:
        return current_user.department_id == ticket.department_id
    return current_user.id == ticket.requester_id
