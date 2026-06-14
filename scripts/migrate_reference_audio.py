"""
Migration script to add name, emotion, content columns to reference_audios table.
"""
import sqlite3
import os

def migrate():
    db_path = os.path.join("data", "srtflow.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(reference_audios)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Existing columns: {columns}")
    
    # Add name column if not exists
    if "name" not in columns:
        print("Adding 'name' column...")
        cursor.execute("ALTER TABLE reference_audios ADD COLUMN name VARCHAR(100)")
        # Set default name from original_filename (without extension)
        cursor.execute("""
            UPDATE reference_audios 
            SET name = SUBSTR(original_filename, 1, 
                CASE 
                    WHEN INSTR(original_filename, '.') > 0 
                    THEN INSTR(original_filename, '.') - 1 
                    ELSE LENGTH(original_filename) 
                END
            ) 
            WHERE name IS NULL
        """)
        print("'name' column added and populated")
    
    # Add emotion column if not exists
    if "emotion" not in columns:
        print("Adding 'emotion' column...")
        cursor.execute("ALTER TABLE reference_audios ADD COLUMN emotion VARCHAR(50)")
        print("'emotion' column added")
    
    # Add content column if not exists
    if "content" not in columns:
        print("Adding 'content' column...")
        cursor.execute("ALTER TABLE reference_audios ADD COLUMN content TEXT")
        print("'content' column added")
    
    conn.commit()
    conn.close()
    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()
