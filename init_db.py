import sqlite3

# Connect to the database file (creates it if it doesn't exist)
conn = sqlite3.connect('users.db')

# Create a cursor to execute SQL commands
cursor = conn.cursor()

# Create the users table
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    password TEXT NOT NULL
)
''')

cursor.execute("ALTER TABLE users ADD COLUMN google_id TEXT;")

# Create the chats table
cursor.execute('''
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_name TEXT NOT NULL,
    chat_history TEXT DEFAULT '',
    FOREIGN KEY(user_id) REFERENCES users(id)
)
''')

# Commit changes and close the connection
conn.commit()
conn.close()

print("Database 'users.db' has been created with the required schema.")
