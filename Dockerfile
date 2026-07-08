FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ["Hybrid Token-Efficient Routing Agent/", "."]

CMD ["python", "main.py"]
