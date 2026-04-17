import aiomysql
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def fix():
    conn = await aiomysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=3306,
        user=os.getenv("MARIADB_USER", "nexusmail"),
        password=os.getenv("MARIADB_PASSWORD", "nexusmail"),
        db=os.getenv("MARIADB_DATABASE", "nexusmail"),
    )
    async with conn.cursor() as cur:
        await cur.execute("""
            ALTER TABLE threads
            ADD COLUMN deadline DATETIME NULL DEFAULT NULL
            AFTER last_message_at
        """)
        print("Added deadline column to threads table")
        await conn.commit()

        # Also update existing INBOX/LOWER values to uppercase to fix enum
        await cur.execute("ALTER TABLE threads MODIFY COLUMN status ENUM('inbox','todo','waiting','done') NOT NULL DEFAULT 'inbox'")
        print("Changed threads.status to lowercase ENUM values (todo/waiting/done)")
        await cur.execute("UPDATE threads SET status = LOWER(status) WHERE status IS NOT NULL")
        print("Normalized existing thread statuses to lowercase")

        await cur.execute("ALTER TABLE emails MODIFY COLUMN status ENUM('inbox','todo','waiting','done') NOT NULL DEFAULT 'inbox'")
        print("Changed emails.status to lowercase ENUM values")
        await cur.execute("UPDATE emails SET status = LOWER(status) WHERE status IS NOT NULL")
        print("Normalized existing email statuses to lowercase")

        # Update alembic version to 003 so it doesn't try to recreate tables
        await cur.execute("SELECT version_num FROM alembic_version LIMIT 1")
        row = await cur.fetchone()
        if row:
            current = row[0]
            if current < "003":
                await cur.execute("UPDATE alembic_version SET version_num = '003'")
                print(f"Updated alembic_version from {current} to 003")
        await conn.commit()
    conn.close()
    print("Done!")

asyncio.run(fix())
