FROM python:3.11-bullseye

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY shelly_emulator.py .

CMD ["python", "shelly_emulator.py"]
