FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаем директорию для временных файлов
RUN mkdir -p /app/temp_videos

CMD ["python", "bot.py"]