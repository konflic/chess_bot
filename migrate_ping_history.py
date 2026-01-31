#!/usr/bin/env python3
"""
Migration script to update the ping_history table schema.
This script adds game_id to the ping_history table to track pings per game instead of per user.
"""

import sqlite3
import os
from configuration import GAMES_DB

def migrate_ping_history():
    """Migrate the ping_history table to include game_id."""

    # Check if database exists
    if not os.path.exists(GAMES_DB):
        print(f"Database {GAMES_DB} does not exist. No migration needed.")
        return

    conn = sqlite3.connect(GAMES_DB)
    cursor = conn.cursor()

    try:
        # Check if the new schema already exists
        cursor.execute("PRAGMA table_info(ping_history)")
        columns = [column[1] for column in cursor.fetchall()]

        if "game_id" in columns:
            print("Database already has the new schema. No migration needed.")
            return

        print("Starting migration of ping_history table...")

        # 1. Rename the old table
        cursor.execute("ALTER TABLE ping_history RENAME TO ping_history_old")
        print("Renamed old table to ping_history_old")

        # 2. Create the new table with game_id
        cursor.execute(
            """
            CREATE TABLE ping_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT,
                player_id INTEGER,
                last_ping_time TIMESTAMP,
                UNIQUE(game_id, player_id)
            )
        """
        )
        print("Created new ping_history table with game_id column")

        # 3. Migrate data from old table
        # Since we don't have game_id for old records, we'll use 'unknown' as a placeholder
        cursor.execute(
            """
            INSERT INTO ping_history (game_id, player_id, last_ping_time)
            SELECT 'unknown', player_id, last_ping_time FROM ping_history_old
        """
        )
        print("Migrated data from old table to new table")

        # 4. Drop the old table
        cursor.execute("DROP TABLE ping_history_old")
        print("Dropped old table")

        # Commit the changes
        conn.commit()
        print("Migration completed successfully!")

    except Exception as e:
        # If something goes wrong, rollback
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_ping_history()
