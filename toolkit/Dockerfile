# Always-on: web app + Telegram bot on a NAS / Raspberry Pi / server.
#   docker build -t tunimix .
#   docker run -d --env-file .env -v $PWD/library:/app/library -p 8765:8765 tunimix web
#   docker run -d --env-file .env -v $PWD/library:/app/library tunimix bot
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENTRYPOINT ["python", "-m", "tunimix"]
CMD ["web", "--host", "0.0.0.0"]
