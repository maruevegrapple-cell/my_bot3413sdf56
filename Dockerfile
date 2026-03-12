FROM python:3.11-slim

WORKDIR /app

# Копируем только requirements.txt сначала
COPY requirements.txt .

# Устанавливаем зависимости с дополнительными флагами
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

# Копируем остальной код
COPY . .

CMD ["python", "bot.py"]