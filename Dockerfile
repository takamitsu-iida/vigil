FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data
# マイグレーションを適用してからサーバーを起動
CMD ["sh", "-c", "alembic upgrade head && uvicorn vigil.main:app --host 0.0.0.0 --port 8000"]
