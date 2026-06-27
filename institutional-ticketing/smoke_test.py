from run import app
from app.extensions import db
from app.models import Department, User

with app.app_context():
    db.drop_all()
    db.create_all()
    from app.services import seed_defaults
    seed_defaults()
    dept = Department.query.first()
    requester = User(full_name='Test Requester', email='requester@example.org', role='requester', department_id=dept.id)
    requester.set_password('Pass@123')
    approver = User(full_name='Test Approver', email='approver@example.org', role='approver', department_id=dept.id)
    approver.set_password('Pass@123')
    staff = User(full_name='Test Staff', email='staff@example.org', role='staff', department_id=dept.id)
    staff.set_password('Pass@123')
    db.session.add_all([requester, approver, staff])
    db.session.commit()

client = app.test_client()

login = client.post('/login', data={'email': 'requester@example.org', 'password': 'Pass@123'}, follow_redirects=True)
assert login.status_code == 200
assert b'Dashboard' in login.data

create_response = client.post(
    '/tickets/create',
    data={
        'title': 'Projector not working',
        'description': 'Classroom projector is not turning on',
        'department_id': '1',
        'category': 'Projector issues',
        'priority': 'High',
        'location': 'Classroom A1',
    },
    follow_redirects=True,
)
assert create_response.status_code == 200
assert b'TSK-' in create_response.data
print('smoke-test-passed')
