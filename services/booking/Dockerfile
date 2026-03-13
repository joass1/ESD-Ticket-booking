FROM python:3.11-slim

WORKDIR /app

COPY services/booking/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/booking/ .

EXPOSE 5002

CMD ["python", "app.py"]
