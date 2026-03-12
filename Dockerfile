FROM python:3.11-slim

WORKDIR /app

# Устанавливаем пакеты напрямую (без requirements.txt)
RUN pip install --no-cache-dir aiogram==3.4.1 pillow==10.2.0 requests==2.31.0 python-dotenv==1.0.0

COPY . .

CMD ["python", "bot.py"]