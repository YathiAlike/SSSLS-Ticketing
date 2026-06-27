# Deployment Guide

## Option 1: Docker Compose
1. Copy `.env.example` to `.env` and update secrets, database URL, and SMTP settings.
2. Run `docker compose up --build -d`.
3. Access the application at `http://localhost:5000`.
4. Run database initialization inside the running container if needed:
   - `docker compose exec web flask init-db`

## Option 2: Manual Linux/VM Deployment
1. Provision Python 3.11+, PostgreSQL, Nginx, and Gunicorn.
2. Clone the project and create a virtual environment.
3. Install requirements using `pip install -r requirements.txt`.
4. Set environment variables from `.env.example`.
5. Initialize the database with `flask init-db`.
6. Start Gunicorn:
   - `gunicorn -w 3 -b 0.0.0.0:5000 run:app`
7. Reverse proxy through Nginx and enable HTTPS.

## Cloud Readiness Notes
- Stateless Flask web tier.
- Externalized database via `DATABASE_URL`.
- Externalized SMTP settings.
- Persistent upload storage can be moved to S3/Azure Blob/GCS by replacing local file storage implementation.
- Suitable for deployment on AWS EC2/ECS, Azure App Service, Google Compute Engine, DigitalOcean App Platform, or Render.

## Security Recommendations
- Change the default administrator password immediately.
- Use a strong `SECRET_KEY`.
- Enable HTTPS and secure cookies.
- Restrict upload size and consider antivirus scanning for files.
- Configure backup and monitoring for the database and uploaded files.
