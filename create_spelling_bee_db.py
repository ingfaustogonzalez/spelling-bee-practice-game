import sqlite3

DB_FILE = "spelling_bee.db"

def create_tables():
    # Connect to or create the database file
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Create tables:
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
    """)

    # Create levels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
    """)

    # Create words table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            context_phrase TEXT NOT NULL,
            level_id INTEGER NOT NULL,
            FOREIGN KEY (level_id) REFERENCES levels(id)
        );
    """)

    # Create sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            level_id INTEGER NOT NULL,
            date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (level_id) REFERENCES levels(id)
        );
    """)

    # Create attempts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            word_id INTEGER NOT NULL,
            correct BOOLEAN NOT NULL,
            duration REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (word_id) REFERENCES words(id)
        );
    """)

    # Create errors table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL UNIQUE,
            misspelling TEXT NOT NULL,
            FOREIGN KEY (attempt_id) REFERENCES attempts(id)
        );
    """)
    
    # Create user_word_state table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_word_state (
            user_id INTEGER NOT NULL,
            word_id INTEGER NOT NULL,
            repetition INTEGER DEFAULT 0,
            ease_factor REAL DEFAULT 2.5,
            interval INTEGER DEFAULT 0,
            next_review TEXT DEFAULT (date('now')),
            PRIMARY KEY (user_id, word_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (word_id) REFERENCES words(id)
        );
    """)
    

    # Commit and close
    conn.commit()
    conn.close()
    
    print("Database and all tables created successfully.")


def populate_levels():
    # Connect to the SQLite database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Insert levels if not already present
    levels = [(1, "Facile"), (2, "Moyen"), (3, "Difficile")]
    cursor.executemany("INSERT OR IGNORE INTO levels (id, name) VALUES (?, ?);", levels)
    
    # Commit and close
    conn.commit()
    conn.close()
    print("Levels inserted successfully.")
    
def add_basic_users():
    # Connect to the SQLite database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create user: admin
    user = [("admin",)]
    cursor.executemany("INSERT OR IGNORE INTO users (name) VALUES (?);", user)
    
    # Commit and close
    conn.commit()
    conn.close()
    
    print("Basic users inserted successfully.")
    

if __name__ == "__main__":
    create_tables()
    populate_levels()
    add_basic_users()