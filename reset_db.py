import asyncio
from sqlalchemy import text
from database.db import engine

async def reset_db():
    async with engine.begin() as conn:
        print("Barcha jadvallar o'chirilmoqda (CASCADE)...")
        # PostgreSQL uchun CASCADE orqali o'chirish
        await conn.execute(text("DROP TABLE IF EXISTS tickets, seats, rows, concerts CASCADE;"))
        try:
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version;"))
        except:
            pass

    print("Bazaga qayta yaratilmoqda...")
    from database.db import init_db
    await init_db()
    print("Tayyor! Baza noldan tiklandi.")

if __name__ == "__main__":
    asyncio.run(reset_db())