import sqlite3
import os

def init_user_joker_table():
    """
    Initialize the UserJoker table for tracking user unlock status
    """
    db_path = 'D:/12DTP-Balatro/app/balatro.db'
    
    if not os.path.exists(db_path):
        print("Database file not found.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create UserJoker table
        cursor.execute('''
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
        print("UserJoker table created successfully")
        
        # Close connection
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error creating UserJoker table: {e}")
        return False

if __name__ == "__main__":
    init_user_joker_table()