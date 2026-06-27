# Institutional Ticketing and Service Request Management System

A complete web-based helpdesk and service request management solution for **Sri Sathya Sai Loka Seva Organizations** and similar institutions.

## Core Features
- Secure login system with password hashing.
- Role-based access control for Requester, Department Approver, Department Staff, and Super Administrator.
- Multi-department routing with default departments and extensible department management.
- Ticket lifecycle management: Open, Under Review, Approved, In Progress, Waiting for Information, Resolved, Closed, and Rejected.
- Department-specific category support for IT, Maintenance, Food/Canteen, Academic, Administration, Hostel, and Transport.
- Attachment support and in-app notification center.
- Audit logs and activity history on every ticket.
- SLA configuration and overdue visibility.
- Feedback and satisfaction rating during closure.
- Responsive Bootstrap dashboard and reporting pages.
- Cloud-ready configuration with PostgreSQL/MySQL support via SQLAlchemy.

## Suggested Users and Roles
### 1. Requester/User
- Submit new tickets.
- Track status.
- Add comments.
- Confirm resolution and close the ticket.

### 2. Department Authority/Approver
- Review department tickets.
- Approve, reject, or assign tickets.
- Add remarks and workflow notes.

### 3. Department Staff/Technician
- View assigned tickets.
- Update progress.
- Mark work as resolved.

### 4. Super Administrator
- Manage users and departments.
- Configure SLA policies.
- View all tickets and reports.

## Technology Stack
- **Backend:** Python Flask
- **Frontend:** Jinja2 + Bootstrap 5
- **Database:** PostgreSQL/MySQL compatible via SQLAlchemy
- **Auth:** Flask-Login + Werkzeug password hashing
- **Deployment:** Gunicorn + Docker/Nginx ready

## Project Structure
```text
institutional-ticketing/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── decorators.py
│   ├── extensions.py
│   ├── models.py
│   ├── services.py
│   ├── routes/
│   ├── static/
│   └── templates/
├── run.py
├── requirements.txt
├── schema.sql
├── UI_OVERVIEW.md
├── DEPLOYMENT.md
├── Dockerfile
└── docker-compose.yml
```

## Default Departments Seeded
- IT Department
- Maintenance Department
- Food/Canteen Department
- Academic Department
- Administration Department
- Hostel Department
- Transport Department

## Local Installation Guide
1. Create and activate a Python virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and update values.
4. Export environment variables or use a tool like `python-dotenv` in your shell.
5. Initialize the database:
   ```bash
   flask --app run init-db
   ```
6. Run the application:
   ```bash
   python run.py
   ```
7. Open `http://localhost:5000`.

## Default Administrator
- Email: value from `DEFAULT_ADMIN_EMAIL`
- Password: value from `DEFAULT_ADMIN_PASSWORD`

Change both immediately in production.

## Ticket Workflow Implemented
1. User raises a request.
2. Ticket is auto-routed to the selected department.
3. Department authority moves the ticket to review, approves, or rejects.
4. Authority assigns the work to department staff.
5. Staff updates progress or requests more information.
6. Staff marks the job resolved.
7. Requester gives feedback and closes the ticket.
8. All events are stored in the activity log and trigger notifications.

## Database Notes
- SQLAlchemy models are the source of truth for runtime.
- `schema.sql` is included for direct database review and manual provisioning.
- The app will auto-create tables on first run, and the CLI command seeds departments, SLA defaults, and the first administrator.

## Email Notifications
In-app notifications are enabled by default.
To activate SMTP email notifications, set:
- `MAIL_ENABLED=true`
- `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`

## Important Enhancements You Can Add Next
- CSRF protection with Flask-WTF.
- Background jobs for escalations and reminder emails using Celery or RQ.
- S3 or cloud object storage for attachments.
- PDF/Excel report exports.
- REST API and mobile app integration.
- SSO with Microsoft/Google institutional identity.

## Deliverables Included
- Complete source code.
- Database schema.
- UI pages and dashboard templates.
- Ticket workflow implementation.
- Installation guide.
- Deployment guide.
