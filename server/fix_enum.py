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
        # Drop the existing enum and recreate with uppercase values matching Python enum names
        await cur.execute("ALTER TABLE emails MODIFY COLUMN status ENUM('INBOX','TODO','WAITING','DONE') NOT NULL DEFAULT 'INBOX'")
        print("Changed emails.status to ENUM('INBOX','TODO','WAITING','DONE')")
        await conn.commit()

        # Update existing values to uppercase
        await cur.execute("UPDATE emails SET status = UPPER(status) WHERE status IS NOT NULL")
        print(f"Updated existing email statuses to uppercase")

        # Also fix threads table
        await cur.execute("ALTER TABLE threads MODIFY COLUMN status ENUM('INBOX','TODO','WAITING','DONE') NOT NULL DEFAULT 'INBOX'")
        print("Changed threads.status to ENUM('INBOX','TODO','WAITING','DONE')")
        await conn.commit()

        await cur.execute("UPDATE threads SET status = UPPER(status) WHERE status IS NOT NULL")
        print(f"Updated existing thread statuses to uppercase")
    conn.close()
    print("Done!")

asyncio.run(fix())
