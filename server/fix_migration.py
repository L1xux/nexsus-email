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
        try:
            await cur.execute("ALTER TABLE emails ADD COLUMN email_thread_id INT NULL")
            print("Added email_thread_id column")
        except Exception as e:
            print(f"Column add: {e}")

        try:
            await cur.execute("CREATE INDEX ix_emails_email_thread_id ON emails (email_thread_id)")
            print("Added index")
        except Exception as e:
            print(f"Index add: {e}")

        try:
            await cur.execute("ALTER TABLE emails ADD CONSTRAINT fk_emails_thread_id FOREIGN KEY (email_thread_id) REFERENCES threads(id) ON DELETE CASCADE")
            print("Added FK constraint")
        except Exception as e:
            print(f"FK add: {e}")

        try:
            await cur.execute("DELETE FROM alembic_version")
            await cur.execute("INSERT INTO alembic_version (version_num) VALUES ('002_add_threads')")
            print("Updated alembic_version to 002_add_threads")
        except Exception as e:
            print(f"Alembic version: {e}")

    conn.close()
    print("Done!")

asyncio.run(fix())
