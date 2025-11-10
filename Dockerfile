FROM python:3.10-slim-buster

WORKDIR /app

COPY app.py .

CMD ["python", "app.py"]