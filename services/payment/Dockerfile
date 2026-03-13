FROM python:3.11-slim

WORKDIR /app

COPY services/payment/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/payment/ .

EXPOSE 5004

CMD ["python", "app.py"]
