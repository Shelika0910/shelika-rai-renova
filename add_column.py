import sqlite3

# Connect to your database
conn = sqlite3.connect(r"C:\Users\acer\Desktop\n\ReNova\renova\db.sqlite3")
cursor = conn.cursor()

# Add the column is_approved
try:
    cursor.execute("ALTER TABLE accounts_customuser ADD COLUMN is_approved BOOLEAN DEFAULT 0;")
    print("Column added successfully!")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column 'is_approved' already exists.")
    else:
        raise

# Commit changes and close
conn.commit()
conn.close()
