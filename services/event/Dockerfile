FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/event/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/event/ .

EXPOSE 5001

CMD ["python", "app.py"]
