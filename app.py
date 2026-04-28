import os

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Post, Task, UserTask
from ai_helper import generate_tasks
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///careers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access that page.'
login_manager.login_message_category = 'warning'

with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ── Auth routes ──────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not email or not password:
            flash('All fields are required.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f'Welcome, {user.username}! Your account has been created.', 'success')
            return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


# ── Main routes ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('index.html', posts=posts)


@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        tags = request.form.get('tags', '').strip()

        if not title or not description:
            flash('Title and description are required.', 'error')
            return render_template('create_post.html')

        task_mode = request.form.get('task_mode', 'ai')

        post = Post(title=title, description=description, tags=tags, user_id=current_user.id)
        db.session.add(post)
        db.session.flush()

        if task_mode == 'manual':
            raw = request.form.get('manual_tasks', '')
            task_list = [line.strip() for line in raw.strip().splitlines() if line.strip()]
            if not task_list:
                flash('Please enter at least one task.', 'error')
                db.session.rollback()
                return render_template('create_post.html')
        else:
            try:
                task_list = generate_tasks(title, description, tags)
            except Exception as e:
                flash(f'AI task generation failed: {e}. Post saved without tasks.', 'warning')
                task_list = []

        for i, content in enumerate(task_list):
            db.session.add(Task(post_id=post.id, content=content, order=i))

        db.session.commit()
        flash('Post created successfully!', 'success')
        return redirect(url_for('post_detail', post_id=post.id))

    return render_template('create_post.html')


@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)

    user_tasks = {}
    is_tracking = False
    if current_user.is_authenticated:
        user_tasks = {
            ut.task_id: ut
            for ut in UserTask.query.filter_by(user_id=current_user.id).all()
        }
        is_tracking = any(t.id in user_tasks for t in post.tasks)

    return render_template('post_detail.html', post=post, is_tracking=is_tracking, user_tasks=user_tasks)


@app.route('/post/<int:post_id>/start', methods=['POST'])
@login_required
def start_tracking(post_id):
    post = Post.query.get_or_404(post_id)

    for task in post.tasks:
        if not UserTask.query.filter_by(user_id=current_user.id, task_id=task.id).first():
            db.session.add(UserTask(user_id=current_user.id, task_id=task.id, completed=False))

    db.session.commit()
    flash('Task group started! Check off tasks as you complete them.', 'success')
    return redirect(url_for('post_detail', post_id=post_id))


@app.route('/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    ut = UserTask.query.filter_by(user_id=current_user.id, task_id=task_id).first_or_404()
    ut.completed = not ut.completed
    db.session.commit()
    return jsonify({'completed': ut.completed})


@app.route('/my-tasks')
@login_required
def my_tasks():
    user_task_list = UserTask.query.filter_by(user_id=current_user.id).all()

    posts_tasks = {}
    for ut in user_task_list:
        post = ut.task.post
        if post.id not in posts_tasks:
            posts_tasks[post.id] = {'post': post, 'tasks': []}
        posts_tasks[post.id]['tasks'].append(ut)

    return render_template('my_tasks.html', posts_tasks=posts_tasks.values())


if __name__ == '__main__':
    app.run(debug=True)
