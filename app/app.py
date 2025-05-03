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
        jokers = conn.execute(f'''
            SELECT
                j.id,
                j.name,
                j.cost,
                r.rarity_name as rarity,
                j.unlock_req,
                t.type_name as type,
                a.activation_name as activation
            FROM Joker j
            JOIN Rarity r ON j.rarity_id = r.id
            JOIN Type t ON j.type_id = t.id
            JOIN Activation a ON j.activation_id = a.id
            ORDER BY {sort_column_sql} {order_sql}
        ''').fetchall()
    except Exception as e:
        # Handle any database errors
        jokers = []
    finally:
        conn.close()
    
    return render_template('jokers.html', 
                          jokers=jokers, 
                          current_sort=sort_by, 
                          current_order=order)

if __name__ == '__main__':
    app.run(debug=True)