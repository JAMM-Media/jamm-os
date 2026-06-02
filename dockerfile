FROM python:3.11-slim

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set workdir
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential libpq-dev libffi-dev

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the codebase
COPY . .

# Expose FastAPI default port
EXPOSE 8000

# Run the app
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app.main:app"]

