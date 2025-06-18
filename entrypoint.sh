#!/bin/bash

# Migrate the database (optional but good)
echo "Running migrations..."
python manage.py migrate

# Collect static files (fixes your problem)
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start the server
echo "Starting server..."
exec gunicorn swif.wsgi:application --bind 0.0.0.0:8002