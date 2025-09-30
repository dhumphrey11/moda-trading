# Finnhub Service Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY ../../shared ./shared

# Copy service code
COPY . .

# Expose port
EXPOSE 8080

# Run the service
CMD ["python", "main.py"]