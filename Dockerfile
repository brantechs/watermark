FROM python:3.12-slim

# appuser ユーザーを作成
RUN useradd -m appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ディレクトリの作成
RUN mkdir -p /app/data/src/temp && \
    chown -R appuser:appuser /app/data/src && \
    chmod -R 755 /app/data/src && \
    chown -R appuser:appuser /app/data/src/temp && \
    chown -R 1000:1000 /app/data/src/temp && \
    chmod -R 755 /app/data/src/temp

# tempディレクトリの存在確認
RUN if [ ! -d /app/data/src/temp ]; then echo "temp directory not created"; exit 1; fi

COPY src/ ./src/
COPY .env .env

CMD ["python", "src/bot.py"]
