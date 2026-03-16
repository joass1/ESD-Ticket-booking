FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/booking_orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/booking_orchestrator/ .

EXPOSE 5010

CMD ["python", "app.py"]
