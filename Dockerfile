FROM python:3.11-slim

WORKDIR /app

# Install sqlite3 CLI (useful for debugging) and dependencies
RUN apt-get update \
	&& apt-get install -y sqlite3 \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run
CMD ["python", "main.py"]
