FROM python:3.11-slim

WORKDIR /app

COPY services/ticket/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ticket/ .

EXPOSE 5006

CMD ["python", "app.py"]
