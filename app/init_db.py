import sqlite3
import os

def init_database():
    """
    Initialize all database tables
    """
    db_path = 'D:/12DTP-Balatro/app/balatro.db'
    
    if not os.path.exists(db_path):
        print("Database file not found.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create User table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS User (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create Feedback table
        cursor.execute('''
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
        print("All database tables created successfully")
        
        # Close connection
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error creating database tables: {e}")
        return False

if __name__ == "__main__":
    init_database()