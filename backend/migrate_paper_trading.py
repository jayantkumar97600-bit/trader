import sqlite3

DB = "trading.db"

conn = sqlite3.connect(DB)
cur = conn.cursor()

existing = {
    row[1]
    for row in cur.execute("PRAGMA table_info(trades)").fetchall()
}

columns = {
    "strategy": "TEXT",
    "execution_timestamp": "TEXT",
    "exit_timestamp": "TEXT",
    "exit_price": "REAL",
    "exit_reason": "TEXT",
    "risk_pct": "REAL",
    "fees": "REAL",
}

for name, sql_type in columns.items():
    if name not in existing:
        cur.execute(
            f"ALTER TABLE trades ADD COLUMN {name} {sql_type}"
        )
        print(f"Added: {name}")
    else:
        print(f"Already exists: {name}")

conn.commit()
conn.close()

print("Migration complete.")
