import sqlite3
import csv

# Database and CSV file paths
DB_FILE = "spelling_bee.db"
CSV_FILE = "words.csv"

# Connect to the SQLite database
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Open and read the CSV file
with open(CSV_FILE, newline='', encoding='utf-8-sig') as csvfile:
    reader = csv.DictReader(csvfile)
    print("CSV Columns found:", reader.fieldnames)
    count = 0
    for row in reader:
        word = row['Épellation'].strip()
        context = row['Contexte'].strip()
        level_id = int(row['Type'])

        cursor.execute("""
            INSERT INTO words (word, context_phrase, level_id)
            VALUES (?, ?, ?);
        """, (word, context, level_id))
        count += 1

# Commit changes and close the connection
conn.commit()
conn.close()

print(f"{count} words imported successfully from {CSV_FILE}.")
