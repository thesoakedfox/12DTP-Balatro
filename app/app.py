"""
Balatro Joker Viewer Application
A Flask web application for viewing and managing Balatro jokers.
"""
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import hashlib
import os


app = Flask(__name__)
# Required for session management
app.secret_key = 'balatro_joker_viewer_secret_key'


def get_db_connection():
    """Create and return a database connection.
    
    Returns:
        sqlite3.Connection: A connection to the balatro database
    """
    conn = sqlite3.connect('D:/12DTP-Balatro/app/balatro.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    """Render the home page.
    
    Returns:
        Rendered home page template or redirect to jokers page if user is logged in
    """
    if 'username' in session:
        return redirect(url_for('jokers'))
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login.
    
    Returns:
        Rendered login page or redirect to jokers page on successful login
    """
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        # Validate form data
        if not username or not password:
            return render_template('login.html', error='Please fill in all required fields')
        
        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        try:
            # Check credentials against database
            user = conn.execute(
                'SELECT * FROM User WHERE username = ? AND password_hash = ?',
                (username, hashed_password)
            ).fetchone()
            
            if user:
                # Login successful
                session['username'] = username
                session['user_id'] = user['id']
                return redirect(url_for('jokers'))
            else:
                # Login failed
                return render_template('login.html', error='Invalid username or password')
        except Exception as e:
            return render_template('login.html', error='An error occurred during login')
        finally:
            conn.close()
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Handle user logout.
    
    Returns:
        Redirect to home page
    """
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect(url_for('home'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handle user registration.
    
    Returns:
        Rendered signup page or redirect to jokers page on successful registration
    """
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        confirm_password = request.form['confirm_password'].strip()
        
        # Validate form data
        if not username or not password:
            return render_template('signup.html', error='Please fill in all required fields')
        
        if password != confirm_password:
            return render_template('signup.html', error='Passwords do not match')
        
        if len(password) < 6:
            return render_template('signup.html', error='Password must be at least 6 characters long')
        
        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        try:
            # Check if username already exists
            existing_user = conn.execute('SELECT * FROM User WHERE username = ?', (username,)).fetchone()
            if existing_user:
                return render_template('signup.html', error='Username already exists')
            
            # Create new user
            conn.execute('INSERT INTO User (username, password_hash) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            
            # Log the user in automatically after signup
            session['username'] = username
            session['user_id'] = conn.execute('SELECT id FROM User WHERE username = ?', (username,)).fetchone()['id']
            
            return redirect(url_for('jokers'))
        except Exception as e:
            return render_template('signup.html', error='An error occurred during registration')
        finally:
            conn.close()
    
    return render_template('signup.html')
@app.route('/jokers')
def jokers():
    """Display the list of jokers with filtering and sorting options.
    
    Returns:
        Rendered jokers page with list of jokers
    """
    # Redirect to login if user is not logged in
    if 'username' not in session:
        return redirect(url_for('login'))
        
    # Get sorting parameters from request
    sort_by = request.args.get('sort_by', 'id')
    order = request.args.get('order', 'asc')
    
    # Get filter parameters
    rarity_filter = request.args.get('rarity', 'all')
    type_filter = request.args.get('type', 'all')
    activation_filter = request.args.get('activation', 'all')
    search_query = request.args.get('search', '').strip()
    unlocked_filter = request.args.get('unlocked', 'all')  # New filter for unlocked status
    
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
    
    # Get session ID for user tracking
    session_id = session.get('user_id')
    if not session_id:
        # Generate a session ID if one doesn't exist
        session_id = os.urandom(16).hex()
        session['user_id'] = session_id
    
    conn = get_db_connection()
    try:
        # Get filter options for the dropdowns
        rarities = conn.execute('SELECT id, rarity_name FROM Rarity ORDER BY id').fetchall()
        types = conn.execute('SELECT id, type_name FROM Type ORDER BY id').fetchall()
        activations = conn.execute('SELECT id, activation_name FROM Activation ORDER BY id').fetchall()
        
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
            LEFT JOIN UserJoker u ON j.id = u.joker_id AND u.session_id = ?
        '''
        
        # Add WHERE conditions based on filters
        where_conditions = []
        params = [session_id]  # Add session ID for user tracking
        
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

        jokers = conn.execute(query, params).fetchall()
    except Exception as e:
        # Handle any database errors
        jokers = []
        rarities = []
        types = []
        activations = []
    finally:
        conn.close()
    
    return render_template(
        'jokers.html',
        jokers=jokers,
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
        joker_id (int): The ID of the joker to display
        
    Returns:
        Rendered template with joker details or 404 page if not found
    """
    # Redirect to login if user is not logged in
    if 'username' not in session:
        return redirect(url_for('login'))
        
    # Use user ID from session if available, otherwise generate session ID
    user_id = session.get('user_id')
    if not user_id:
        # Generate a session ID if one doesn't exist
        session_id = os.urandom(16).hex()
    else:
        session_id = f"user_{user_id}"
    
    conn = get_db_connection()
    try:
        # Get the specific joker
        joker = conn.execute('''
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
            LEFT JOIN UserJoker u ON j.id = u.joker_id AND u.session_id = ?
            WHERE j.id = ?
        ''', (session_id, joker_id)).fetchone()
        
        if joker is None:
            # Return 404 if joker not found
            conn.close()
            return render_template('404.html'), 404
            
    except Exception as e:
        # Handle database errors
        joker = None
        print(f"Database error: {e}")
    finally:
        conn.close()
    
    return render_template('joker_detail.html', joker=joker)


@app.route('/toggle_unlock/<int:joker_id>')
def toggle_unlock(joker_id):
    """Toggle the unlock status of a joker for the current user.
    
    Args:
        joker_id (int): The ID of the joker to toggle unlock status for
        
    Returns:
        Redirect back to the referring page or jokers page
    """
    # Redirect to login if user is not logged in
    if 'username' not in session:
        return redirect(url_for('login'))
        
    # Use user ID from session if available, otherwise generate session ID
    user_id = session.get('user_id')
    if not user_id:
        # Generate a session ID if one doesn't exist
        session_id = os.urandom(16).hex()
    else:
        session_id = f"user_{user_id}"
    
    conn = get_db_connection()
    try:
        # Check if there's already an entry for this joker and session
        existing = conn.execute('''
            SELECT unlocked FROM UserJoker 
            WHERE joker_id = ? AND session_id = ?
        ''', (joker_id, session_id)).fetchone()
        
        if existing:
            # Toggle the unlocked status
            new_status = 0 if existing['unlocked'] == 1 else 1
            conn.execute('''
                UPDATE UserJoker 
                SET unlocked = ?, updated_at = CURRENT_TIMESTAMP
                WHERE joker_id = ? AND session_id = ?
            ''', (new_status, joker_id, session_id))
        else:
            # Create a new entry with unlocked = 1
            conn.execute('''
                INSERT INTO UserJoker (joker_id, session_id, unlocked)
                VALUES (?, ?, 1)
            ''', (joker_id, session_id))
            
        conn.commit()
    except Exception as e:
        print(f"Error toggling unlock status: {e}")
    finally:
        conn.close()
    
    # Redirect back to the referring page, or to jokers page if not available
    referrer = request.headers.get('Referer')
    if referrer:
        return redirect(referrer)
    return redirect(url_for('jokers'))

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    """Handle feedback form submission"""
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        feedback_text = request.form.get('feedback', '').strip()
        rating = request.form.get('rating', '').strip()
        
        # Validate required fields
        if not feedback_text or not rating:
            return render_template('feedback.html', 
                                message='Please fill in all required fields.', 
                                message_type='error')
        
        # Hash sensitive data for privacy
        hashed_name = hashlib.sha256(name.encode()).hexdigest() if name else None
        hashed_email = hashlib.sha256(email.encode()).hexdigest() if email else None
        
        # Store feedback in database
        try:
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO Feedback (name_hash, email_hash, feedback, rating)
                VALUES (?, ?, ?, ?)
            ''', (hashed_name, hashed_email, feedback_text, int(rating)))
            
            conn.commit()
            conn.close()
            
            return render_template(
        'feedback.html',
        message='Thank you for your feedback!',
        message_type='success'
    )
                                
        except Exception as e:
            return render_template(
        'feedback.html',
        message='An error occurred while submitting your feedback. Please try again.',
        message_type='error'
    )
    
    # For GET requests, show the form
    return render_template('feedback.html')

# Custom 404 error handler
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors.
    
    Args:
        e: The error object
        
    Returns:
        Rendered 404 page with 404 status code
    """
    return render_template('404.html'), 404

if __name__ == '__main__':
    # Initialize database tables if they don't exist
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
        
        # Create UserJoker table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS UserJoker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                joker_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                unlocked INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (joker_id) REFERENCES Joker (id),
                UNIQUE(joker_id, session_id)
            )
        ''')
        
        conn.commit()
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        conn.close()
    
    app.run(debug=True)