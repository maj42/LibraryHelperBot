# Use Python base image
FROM python:3.11

# Set working directory inside container
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code, but secrets will be mounted separately
COPY . .

# Start the bot
CMD ["python", "main.py"]