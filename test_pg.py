import asyncio
import asyncpg

async def test():
    # Попробуй разные варианты хоста
    hosts = ["localhost", "127.0.0.1", "::1"]
    
    for host in hosts:
        try:
            print(f"Пробуем host={host}...")
            conn = await asyncpg.connect(
                host=host,
                port=5432,
                user="postgres",
                password="QW123098",
                database="postgres"
            )
            print(f"✅ Подключение успешно через {host}!")
            await conn.close()
            return
        except Exception as e:
            print(f"❌ Ошибка через {host}: {e}")
    
    # Если ничего не помогло, попробуем через .pgpass или без указания хоста
    try:
        print("Пробуем без указания хоста...")
        conn = await asyncpg.connect(
            user="postgres",
            password="QW123098",
            database="postgres"
        )
        print("✅ Подключение успешно (через сокет)!")
        await conn.close()
    except Exception as e:
        print(f"❌ Ошибка: {e}")

asyncio.run(test())