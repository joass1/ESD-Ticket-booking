FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/charging/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/charging/ .

EXPOSE 5008

CMD ["python", "app.py"]
