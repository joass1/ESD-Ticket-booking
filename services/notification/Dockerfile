FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/notification/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/notification/ .

EXPOSE 5005

CMD ["python", "app.py"]
