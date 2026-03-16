FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/waitlist/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/waitlist/ .

EXPOSE 5007

CMD ["python", "app.py"]
