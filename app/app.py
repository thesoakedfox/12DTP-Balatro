from flask import Flask, render_template
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
    conn = get_db_connection()
    jokers = conn.execute('''
        SELECT
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
    ''').fetchall()
    conn.close()
    return render_template('jokers.html', jokers=jokers)

if __name__ == '__main__':
    app.run(debug=True)