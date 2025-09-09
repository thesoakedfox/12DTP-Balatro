"""Flask application for Balatro joker viewer."""

import hashlib
import os
import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = 'balatro_joker_viewer_secret_key'

# Simple input limits to prevent abuse/DoS
MAX_USERNAME_LENGTH = 64
MAX_PASSWORD_LENGTH = 256


def get_db_connection():
    """Get database connection with row factory."""
    db_path = os.path.join(os.path.dirname(__file__), 'balatro.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# Convenience DB helpers
def query_db(query, params=(), one=False):
    """Run a SELECT query and return rows.

    Args:
        query: SQL query string with placeholders (?).
        params: Tuple/list of parameters for the query.
        one: When True, return only the first row (or None).

    Returns:
        list[sqlite3.Row] | sqlite3.Row | None
    """
    conn = get_db_connection()
    try:
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def execute_db(query, params=()):
    """Execute a write query (INSERT/UPDATE/DELETE) and commit.

    Returns lastrowid when available.
    """
    conn = get_db_connection()
    try:
        cur = conn.execute(query, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def query_one(query, params=()):
    """Shorthand for query_db(..., one=True)."""
    return query_db(query, params, one=True)


def query_value(query, params=(), default=None):
    """Return the first column of the first row, or default."""
    row = query_db(query, params, one=True)
    return (row[0] if row is not None else default)


@app.route('/')
def home():
    """Home page route."""
    if 'username' in session:
        return redirect(url_for('jokers'))
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        # Validate form data
        if not username or not password:
            return render_template(
                'login.html',
                error='Please fill in all required fields'
            )

        # Enforce maximum lengths
        if len(username) > MAX_USERNAME_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
            return render_template(
                'login.html',
                error='Invalid username or password'
            )

        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        try:
            # Check credentials against database
            user = query_one(
                'SELECT * FROM User WHERE username = ? AND password_hash = ?',
                (username, hashed_password)
            )

            if user:
                # Login successful
                session['username'] = username
                session['user_id'] = user['id']
                return redirect(url_for('jokers'))
            else:
                # Login failed
                return render_template(
                    'login.html',
                    error='Invalid username or password'
                )
        except Exception:
            return render_template(
                'login.html',
                error='An error occurred during login'
            )

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Handle user logout."""
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect(url_for('home'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handle user registration."""
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        confirm_password = request.form['confirm_password'].strip()

        # Validate form data
        if not username or not password:
            return render_template(
                'signup.html',
                error='Please fill in all required fields'
            )

        # Enforce maximum lengths
        if len(username) > MAX_USERNAME_LENGTH:
            return render_template(
                'signup.html',
                error=f'Username must be at most {MAX_USERNAME_LENGTH} characters long'
            )

        if len(password) > MAX_PASSWORD_LENGTH:
            return render_template(
                'signup.html',
                error='Password is too long'
            )

        if password != confirm_password:
            return render_template(
                'signup.html',
                error='Passwords do not match'
            )

        if len(password) < 6:
            return render_template(
                'signup.html',
                error='Password must be at least 6 characters long'
            )

        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        try:
            # Check if username already exists
            existing_user = query_one(
                'SELECT 1 FROM User WHERE username = ?',
                (username,)
            )
            if existing_user:
                return render_template(
                    'signup.html',
                    error='Username already exists'
                )

            # Create new user and capture inserted id
            user_id = execute_db(
                'INSERT INTO User (username, password_hash) VALUES (?, ?)',
                (username, hashed_password)
            )

            # Log the user in automatically after signup
            session['username'] = username
            session['user_id'] = user_id

            return redirect(url_for('jokers'))
        except Exception:
            return render_template(
                'signup.html',
                error='An error occurred during registration'
            )

    return render_template('signup.html')


@app.route('/jokers')
def jokers():
    """Display jokers with filtering and sorting options.

    Returns:
        Rendered jokers page with list of jokers.
    """
    # Check if user is logged in
    if 'username' not in session:
        return redirect(url_for('login'))

    # Sort parameters
    sort_by = request.args.get('sort_by', 'id')
    order = request.args.get('order', 'asc')

    # Get filter parameters
    rarity_filter = request.args.get('rarity', 'all')
    type_filter = request.args.get('type', 'all')
    activation_filter = request.args.get('activation', 'all')
    search_query = request.args.get('search', '').strip()
    unlocked_filter = request.args.get('unlocked', 'all')

    # Limit search query length to prevent abuse
    if len(search_query) > 100:
        search_query = search_query[:100]

    # Validate sort parameters to prevent SQL injection
    valid_sort_columns = ['id', 'name', 'cost', 'rarity_id']
    valid_orders = ['asc', 'desc']

    if sort_by not in valid_sort_columns:
        sort_by = 'id'

    if order not in valid_orders:
        order = 'asc'

    # Map sort_by values to column names for display
    sort_columns_map = {
        'id': 'j.id',
        'name': 'j.name',
        'cost': 'j.cost',
        'rarity_id': 'r.rarity_name'
    }

    order_sql = 'ASC' if order == 'asc' else 'DESC'
    sort_column_sql = sort_columns_map.get(sort_by, 'j.id')

    # Use authenticated user's ID for tracking
    user_id = session.get('user_id')

    try:
        # Get filter options for the dropdowns
        rarities = query_db('SELECT id, rarity_name FROM Rarity ORDER BY id')
        types = query_db('SELECT id, type_name FROM Type ORDER BY id')
        activations = query_db('SELECT id, activation_name FROM Activation ORDER BY id')

        # Build the query with optional filters
        base_query = '''
            SELECT
                j.id,
                j.name,
                j.cost,
                r.rarity_name as rarity,
                j.unlock_req,
                t.type_name as type,
                a.activation_name as activation,
                j.sprite,
                u.unlocked as unlocked
            FROM Joker j
            JOIN Rarity r ON j.rarity_id = r.id
            JOIN Type t ON j.type_id = t.id
            JOIN Activation a ON j.activation_id = a.id
            LEFT JOIN UserJoker u ON j.id = u.joker_id AND u.user_id = ?
        '''

        # Add WHERE conditions based on filters
        where_conditions = []
        params = [user_id]

        if rarity_filter != 'all':
            where_conditions.append('r.id = ?')
            params.append(rarity_filter)

        if type_filter != 'all':
            where_conditions.append('t.id = ?')
            params.append(type_filter)

        if activation_filter != 'all':
            where_conditions.append('a.id = ?')
            params.append(activation_filter)

        if search_query:
            where_conditions.append('j.name LIKE ?')
            params.append(f'%{search_query}%')

        # Filter by unlocked status
        if unlocked_filter == 'unlocked':
            where_conditions.append('u.unlocked = 1')
        elif unlocked_filter == 'locked':
            # Either no entry in UserJoker table or unlocked = 0
            where_conditions.append('(u.unlocked IS NULL OR u.unlocked = 0)')

        query = base_query
        if where_conditions:
            query += ' WHERE ' + ' AND '.join(where_conditions)

        query += f' ORDER BY {sort_column_sql} {order_sql}'

        jokers_result = query_db(query, params)
    except Exception:
        # Handle any database errors
        jokers_result = []
        rarities = []
        types = []
        activations = []

    return render_template(
        'jokers.html',
        jokers=jokers_result,
        rarities=rarities,
        types=types,
        activations=activations,
        current_sort=sort_by,
        current_order=order,
        rarity_filter=rarity_filter,
        type_filter=type_filter,
        activation_filter=activation_filter,
        search_query=search_query,
        unlocked_filter=unlocked_filter
    )


@app.route('/joker/<int:joker_id>')
def joker_detail(joker_id):
    """Display details for a specific joker.

    Args:
        joker_id (int): The ID of the joker to display.

    Returns:
        Rendered template with joker details or 404 page if not found.
    """
    # Redirect to login if user is not logged in
    if 'username' not in session:
        return redirect(url_for('login'))

    # Use authenticated user's ID
    user_id = session.get('user_id')

    try:
        # Get the specific joker
        joker = query_one('''
            SELECT
                j.id,
                j.name,
                j.cost,
                j.unlock_req,
                r.rarity_name,
                r.id as rarity_id,
                t.type_name,
                t.id as type_id,
                a.activation_name,
                a.id as activation_id,
                j.sprite,
                u.unlocked as unlocked
            FROM Joker j
            JOIN Rarity r ON j.rarity_id = r.id
            JOIN Type t ON j.type_id = t.id
            JOIN Activation a ON j.activation_id = a.id
            LEFT JOIN UserJoker u ON j.id = u.joker_id AND u.user_id = ?
            WHERE j.id = ?
        ''', (user_id, joker_id))

        if joker is None:
            # Return 404 if joker not found
            return render_template('404.html'), 404

    except Exception as e:
        # Handle database errors
        joker = None
        print(f"Database error: {e}")

    return render_template('joker_detail.html', joker=joker)


@app.route('/toggle_unlock/<int:joker_id>')
def toggle_unlock(joker_id):
    """Toggle the unlock status of a joker for the current user.

    Args:
        joker_id (int): The ID of the joker to toggle unlock status for.

    Returns:
        Redirect back to the referring page or jokers page, or JSON for AJAX.
    """
    # Redirect to login if user is not logged in
    if 'username' not in session:
        return redirect(url_for('login'))

    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Use authenticated user's ID
    user_id = session.get('user_id')

    try:
        # Check if there's already an entry for this joker and user
        existing = query_one('''
            SELECT unlocked FROM UserJoker
            WHERE joker_id = ? AND user_id = ?
        ''', (joker_id, user_id))

        if existing:
            # Toggle the unlocked status
            new_status = 0 if existing['unlocked'] == 1 else 1
            execute_db('''
                UPDATE UserJoker
                SET unlocked = ?, updated_at = CURRENT_TIMESTAMP
                WHERE joker_id = ? AND user_id = ?
            ''', (new_status, joker_id, user_id))
        else:
            # Create a new entry with unlocked = 1
            execute_db('''
                INSERT INTO UserJoker (joker_id, user_id, unlocked)
                VALUES (?, ?, 1)
            ''', (joker_id, user_id))

        # If this is an AJAX request, return an empty 200
        if is_ajax:
            return '', 200

    except Exception as e:
        print(f"Error toggling unlock status: {e}")
        if is_ajax:
            return '', 500

    # For non-AJAX requests, redirect back to referring page or jokers page
    if not is_ajax:
        referrer = request.headers.get('Referer')
        if referrer:
            return redirect(referrer)
        return redirect(url_for('jokers'))


@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    """Handle feedback form submission."""
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        feedback_text = request.form.get('feedback', '').strip()
        rating = request.form.get('rating', '').strip()

        # Validate required fields
        if not feedback_text or not rating:
            return render_template(
                'feedback.html',
                message='Please fill in all required fields.',
                message_type='error'
            )

        # Hash sensitive data for privacy
        hashed_name = (
            hashlib.sha256(name.encode()).hexdigest() if name else None
        )
        hashed_email = (
            hashlib.sha256(email.encode()).hexdigest() if email else None
        )

        # Store feedback in database
        try:
            execute_db('''
                INSERT INTO Feedback (name_hash, email_hash, feedback, rating)
                VALUES (?, ?, ?, ?)
            ''', (hashed_name, hashed_email, feedback_text, int(rating)))

            return render_template(
                'feedback.html',
                message='Thank you for your feedback!',
                message_type='success'
            )

        except Exception:
            return render_template(
                'feedback.html',
                message=('An error occurred while submitting feedback. '
                         'Please try again.'),
                message_type='error'
            )

    # For GET requests, show the form
    return render_template('feedback.html')


@app.errorhandler(404)
def page_not_found(e):
    """Custom 404 error handler."""
    return render_template('404.html'), 404


def create_tables():
    """Initialize database tables if they don't exist."""
    conn = get_db_connection()
    try:
        # Create User table for authentication
        conn.execute('''
            CREATE TABLE IF NOT EXISTS User (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create Feedback table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_hash TEXT,
                email_hash TEXT,
                feedback TEXT NOT NULL,
                rating INTEGER NOT NULL,
                submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create UserJoker table (user <-> joker many-to-many)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS UserJoker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                joker_id INTEGER NOT NULL,
                unlocked INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES User (id),
                FOREIGN KEY (joker_id) REFERENCES Joker (id),
                UNIQUE(user_id, joker_id)            )
        ''')

        conn.commit()
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        conn.close()


if __name__ == '__main__':
    create_tables()
    app.run(debug=True)
