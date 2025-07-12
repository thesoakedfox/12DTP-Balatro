from flask import Flask, render_template, request
import sqlite3

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

# Custom 404 error handler
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)