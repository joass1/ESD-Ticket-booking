FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/seat/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/seat/ .

EXPOSE 5003

CMD ["python", "app.py"]
