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
        await cur.execute("ALTER TABLE emails MODIFY COLUMN body_html LONGTEXT")
        print("Changed body_html to LONGTEXT")
        await cur.execute("ALTER TABLE emails MODIFY COLUMN body_text LONGTEXT")
        print("Changed body_text to LONGTEXT")
    conn.close()
    print("Done!")

asyncio.run(fix())
