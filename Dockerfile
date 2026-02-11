FROM python:3.11-slim

# Установка необходимых системных библиотек
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Команда для запуска бота
CMD ["python", "bot.py"]
