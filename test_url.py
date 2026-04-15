import asyncpg
import asyncio

async def main():
    try:
        conn = await asyncpg.connect(
            user='botuser',
            password='botpass123',
            database='botdb',
            host='localhost'
        )
        print('✅ Connected!')
        await conn.close()
    except Exception as e:
        print(f'Error: {e}')

asyncio.run(main())