import sqlite3
import os

db_path = "h:/WORK/I/kvm-dashboard/backend/kvm_test.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE devices ADD COLUMN endpoint_count INTEGER DEFAULT 0")
        conn.commit()
        print("Success: Added endpoint_count to devices table.")
    except sqlite3.OperationalError as e:
        print(f"Error (maybe already exists): {e}")
    finally:
        conn.close()
else:
    print(f"File not found: {db_path}")
