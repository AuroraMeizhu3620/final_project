"""
LaunchShare -- full functional test suite.
Run with:  python test_app.py
"""
import os, sys, json, tempfile

os.environ.setdefault('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY', ''))
os.environ.setdefault('SECRET_KEY', 'test-secret-key')

import app as app_module
from models import db, User, Post, Task, UserTask

# Use a temp file so every request shares the same DB connection pool
tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
tmp.close()
DB_PATH = tmp.name

app_module.app.config['TESTING'] = True
app_module.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app_module.app.config['WTF_CSRF_ENABLED'] = False

with app_module.app.app_context():
    db.drop_all()
    db.create_all()

client = app_module.app.test_client()
client.testing = True

results = []

def check(name, condition, detail=''):
    label = 'PASS' if condition else 'FAIL'
    results.append(condition)
    print(f'  [{label}] {name}' + (f' - {detail}' if detail else ''))
    return condition

def section(title):
    print(f'\n-- {title} --')

def login(username='testuser', password='password123'):
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'username': username, 'password': password})

def logout():
    client.get('/logout', follow_redirects=True)


# ── 1. Public pages ───────────────────────────────────────────────────────────
section('1. Public Pages')

r = client.get('/')
check('Home page loads', r.status_code == 200)
check('LaunchShare branding present', b'LaunchShare' in r.data)
check('Hero tagline present', b'Launch' in r.data)

r = client.get('/login')
check('Login page loads', r.status_code == 200)

r = client.get('/register')
check('Register page loads', r.status_code == 200)


# ── 2. Auth guards ────────────────────────────────────────────────────────────
section('2. Auth Guards (logged out)')

logout()
r = client.get('/create', follow_redirects=False)
check('GET /create redirects to login', r.status_code == 302 and b'login' in r.headers['Location'].encode())

r = client.get('/my-tasks', follow_redirects=False)
check('GET /my-tasks redirects to login', r.status_code == 302)

r = client.post('/post/1/start', follow_redirects=False)
check('POST /start redirects to login', r.status_code == 302)


# ── 3. Registration ───────────────────────────────────────────────────────────
section('3. Registration')

logout()
r = client.post('/register', data={
    'username': 'testuser',
    'email': 'test@babson.edu',
    'password': 'password123',
    'confirm_password': 'password123',
}, follow_redirects=True)
check('Valid registration succeeds (200)', r.status_code == 200)
check('Redirected to feed after register', b'LaunchShare' in r.data)

with app_module.app.app_context():
    user = User.query.filter_by(username='testuser').first()
    check('User saved in database', user is not None)
    check('Password is hashed', user and user.password_hash != 'password123')

logout()
r = client.post('/register', data={
    'username': 'testuser',
    'email': 'other@babson.edu',
    'password': 'password123',
    'confirm_password': 'password123',
}, follow_redirects=True)
check('Duplicate username rejected', b'taken' in r.data.lower())

logout()
r = client.post('/register', data={
    'username': 'user2',
    'email': 'test@babson.edu',
    'password': 'password123',
    'confirm_password': 'password123',
}, follow_redirects=True)
check('Duplicate email rejected', b'already' in r.data.lower())

logout()
r = client.post('/register', data={
    'username': 'user3', 'email': 'u3@babson.edu',
    'password': 'abc', 'confirm_password': 'abc',
}, follow_redirects=True)
check('Short password rejected', b'6' in r.data or b'characters' in r.data.lower())

logout()
r = client.post('/register', data={
    'username': 'user4', 'email': 'u4@babson.edu',
    'password': 'password123', 'confirm_password': 'wrong',
}, follow_redirects=True)
check('Mismatched passwords rejected', b'match' in r.data.lower())


# ── 4. Login / Logout ─────────────────────────────────────────────────────────
section('4. Login / Logout')

logout()
r = client.post('/login', data={'username': 'testuser', 'password': 'password123'}, follow_redirects=True)
check('Valid login succeeds', r.status_code == 200)
check('Welcome message shown', b'Welcome' in r.data or b'testuser' in r.data)

logout()
r = client.post('/login', data={'username': 'testuser', 'password': 'wrongpass'}, follow_redirects=True)
check('Wrong password rejected', b'invalid' in r.data.lower())

logout()
r = client.post('/login', data={'username': 'nobody', 'password': 'password123'}, follow_redirects=True)
check('Non-existent user rejected', b'invalid' in r.data.lower())

login()
r = client.get('/logout', follow_redirects=True)
check('Logout works', r.status_code == 200)
check('Logout confirmation shown', b'logged out' in r.data.lower())


# ── 5. Create Post -- Manual Tasks ───────────────────────────────────────────
section('5. Create Post (Manual Tasks)')

login()
r = client.get('/create')
check('Create page loads when logged in', r.status_code == 200)
check('AI/Manual toggle present', b'task_mode' in r.data)

r = client.post('/create', data={
    'title': 'How I got my first internship',
    'description': 'I cold-emailed 50 companies and followed up.',
    'tags': 'internship, networking',
    'task_mode': 'manual',
    'manual_tasks': 'Update your LinkedIn\nEmail 5 alumni\nApply to 3 roles',
}, follow_redirects=True)
check('Manual post created (200)', r.status_code == 200)
check('Post detail shows title', b'How I got my first internship' in r.data)
check('Tasks appear on post detail', b'Update your LinkedIn' in r.data)

with app_module.app.app_context():
    post = Post.query.filter_by(title='How I got my first internship').first()
    check('Post saved in DB', post is not None)
    check('Author linked to post', post and post.user_id is not None)
    check('3 tasks saved', post and len(post.tasks) == 3)
    post_id = post.id if post else None

login()
r = client.post('/create', data={
    'title': '', 'description': 'content',
    'task_mode': 'manual', 'manual_tasks': 'A task',
}, follow_redirects=True)
check('Empty title rejected', b'required' in r.data.lower())

login()
r = client.post('/create', data={
    'title': 'No tasks', 'description': 'content',
    'task_mode': 'manual', 'manual_tasks': '',
}, follow_redirects=True)
check('Empty manual task list rejected', b'task' in r.data.lower())


# ── 6. Feed ───────────────────────────────────────────────────────────────────
section('6. Feed')

r = client.get('/')
check('Feed loads', r.status_code == 200)
check('Post appears in feed', b'How I got my first internship' in r.data)
check('Author shown on card', b'testuser' in r.data)
check('Task count shown', b'tasks' in r.data)


# ── 7. Post Detail ────────────────────────────────────────────────────────────
section('7. Post Detail')

login()
r = client.get(f'/post/{post_id}')
check('Post detail loads', r.status_code == 200)
check('Author badge shown', b'testuser' in r.data)
check('Tasks listed on detail page', b'Update your LinkedIn' in r.data)
check('Start Mission button present', b'Start' in r.data)

r = client.get('/post/99999')
check('Non-existent post returns 404', r.status_code == 404)


# ── 8. Task Tracking ─────────────────────────────────────────────────────────
section('8. Task Tracking')

login()
r = client.post(f'/post/{post_id}/start', follow_redirects=True)
check('Start tracking succeeds', r.status_code == 200)
check('Confirmation message shown', b'mission' in r.data.lower() or b'task' in r.data.lower())

with app_module.app.app_context():
    user = User.query.filter_by(username='testuser').first()
    uts = UserTask.query.filter_by(user_id=user.id).all()
    check('3 UserTask rows created', len(uts) == 3, f'found {len(uts)}')
    check('All tasks start uncompleted', all(not ut.completed for ut in uts))

# Starting same post again should not duplicate
r = client.post(f'/post/{post_id}/start', follow_redirects=True)
check('Re-starting same post does not error', r.status_code == 200)

with app_module.app.app_context():
    user = User.query.filter_by(username='testuser').first()
    uts = UserTask.query.filter_by(user_id=user.id).all()
    check('Still only 3 UserTask rows (no duplicates)', len(uts) == 3, f'found {len(uts)}')


# ── 9. Toggle Task ────────────────────────────────────────────────────────────
section('9. Toggle Task Completion')

with app_module.app.app_context():
    user = User.query.filter_by(username='testuser').first()
    ut = UserTask.query.filter_by(user_id=user.id).first()
    task_id = ut.task_id if ut else None

check('UserTask found for toggle test', task_id is not None)

if task_id:
    login()
    r = client.post(f'/task/{task_id}/toggle')
    check('Toggle returns 200', r.status_code == 200)
    data = json.loads(r.data)
    check('Toggle marks task completed', data.get('completed') == True)

    r = client.post(f'/task/{task_id}/toggle')
    data = json.loads(r.data)
    check('Toggle again uncompletes task', data.get('completed') == False)

    logout()
    r = client.post(f'/task/{task_id}/toggle')
    check('Toggle blocked when logged out', r.status_code == 302)


# ── 10. My Missions page ──────────────────────────────────────────────────────
section('10. My Missions Page')

login()
r = client.get('/my-tasks')
check('My Missions page loads', r.status_code == 200)
check('Mission group shown', b'How I got my first internship' in r.data)
check('XP banner present', b'XP' in r.data)
check('Progress bar present', b'progress' in r.data.lower())
check('Cadet level shown (new user)', b'Cadet' in r.data)


# ── 11. AI Task Generation ────────────────────────────────────────────────────
section('11. AI Task Generation (live API call)')

api_key = os.getenv('OPENAI_API_KEY', '')
if not api_key:
    print('  [SKIP] No OPENAI_API_KEY in .env')
else:
    try:
        from ai_helper import generate_tasks
        tasks = generate_tasks(
            'How to network at career fairs',
            'I attended 5 career fairs. Here is what worked for me.',
            'networking, career fair'
        )
        check('AI returns a list', isinstance(tasks, list))
        check('AI returns 4-8 tasks', 4 <= len(tasks) <= 8, f'got {len(tasks)}')
        check('Each task is a non-empty string', all(isinstance(t, str) and len(t) > 5 for t in tasks))
        if tasks:
            print(f'     Sample task: "{tasks[0]}"')
    except Exception as e:
        check('AI task generation', False, str(e))


# ── Cleanup & Summary ─────────────────────────────────────────────────────────
try:
    os.unlink(DB_PATH)
except Exception:
    pass

print('\n' + '=' * 55)
passed = sum(results)
total  = len(results)
failed = total - passed
print(f'  Results: {passed}/{total} passed', end='')
if failed:
    print(f'  |  {failed} FAILED  <--')
else:
    print('  -- All tests passed!')
print('=' * 55)

sys.exit(0 if failed == 0 else 1)
