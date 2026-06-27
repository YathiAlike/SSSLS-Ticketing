from pathlib import Path

import click
from flask import Flask
from flask_login import current_user

from .config import Config
from .extensions import db, login_manager
from .models import Notification
from .services import CATEGORY_MAP, escalation_candidates, notify_users, seed_defaults


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.tickets import tickets_bp
    from .routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_globals():
        unread_notifications = []
        if current_user.is_authenticated:
            unread_notifications = (
                Notification.query.filter_by(user_id=current_user.id, is_read=False)
                .order_by(Notification.created_at.desc())
                .limit(5)
                .all()
            )
        return {
            "category_map": CATEGORY_MAP,
            "unread_notifications": unread_notifications,
            "app_name": app.config["APP_NAME"],
            "company_name": app.config["COMPANY_NAME"],
        }

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        seed_defaults()
        click.echo("Database initialized and default records created.")

    @app.cli.command("run-escalations")
    def run_escalations():
        candidates = escalation_candidates()
        total = 0
        for ticket in candidates:
            recipients = [ticket.requester]
            if ticket.approver:
                recipients.append(ticket.approver)
            if ticket.assignee:
                recipients.append(ticket.assignee)
            notify_users(
                recipients,
                ticket,
                f"Escalation alert: Ticket {ticket.ticket_number} is overdue based on configured SLA.",
            )
            total += 1
        click.echo(f"Escalation notifications processed for {total} overdue ticket(s).")

    with app.app_context():
        db.create_all()
        seed_defaults()

    return app
