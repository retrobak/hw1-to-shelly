FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY shelly_emulator.py .

# Run app
CMD ["python", "shelly_emulator.py"]
