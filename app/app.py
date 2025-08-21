from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import hashlib
import os

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('D:/12DTP-Balatro/app/balatro.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/jokers')
def jokers():
    # Get sorting parameters from request
    sort_by = request.args.get('sort_by', 'id')
    order = request.args.get('order', 'asc')
    
    # Get filter parameters
    rarity_filter = request.args.get('rarity', 'all')
    type_filter = request.args.get('type', 'all')
    activation_filter = request.args.get('activation', 'all')
    search_query = request.args.get('search', '').strip()
    
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
                j.sprite
            FROM Joker j
            JOIN Rarity r ON j.rarity_id = r.id
            JOIN Type t ON j.type_id = t.id
            JOIN Activation a ON j.activation_id = a.id
        '''
        
        # Add WHERE conditions based on filters
        where_conditions = []
        params = []
        
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
    
    return render_template('jokers.html', 
                          jokers=jokers,
                          rarities=rarities,
                          types=types,
                          activations=activations,
                          current_sort=sort_by, 
                          current_order=order,
                          rarity_filter=rarity_filter,
                          type_filter=type_filter,
                          activation_filter=activation_filter,
                          search_query=search_query)

@app.route('/joker/<int:joker_id>')
def joker_detail(joker_id):
    """Display details for a specific joker"""
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
                j.sprite
            FROM Joker j
            JOIN Rarity r ON j.rarity_id = r.id
            JOIN Type t ON j.type_id = t.id
            JOIN Activation a ON j.activation_id = a.id
            WHERE j.id = ?
        ''', (joker_id,)).fetchone()
        
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
                CREATE TABLE IF NOT EXISTS Feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name_hash TEXT,
                    email_hash TEXT,
                    feedback TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                INSERT INTO Feedback (name_hash, email_hash, feedback, rating)
                VALUES (?, ?, ?, ?)
            ''', (hashed_name, hashed_email, feedback_text, int(rating)))
            
            conn.commit()
            conn.close()
            
            return render_template('feedback.html', 
                                message='Thank you for your feedback!', 
                                message_type='success')
                                
        except Exception as e:
            return render_template('feedback.html', 
                                message='An error occurred while submitting your feedback. Please try again.', 
                                message_type='error')
    
    # For GET requests, show the form
    return render_template('feedback.html')

# Custom 404 error handler
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)