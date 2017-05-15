web: gunicorn proj333.wsgi:application --log-file -
worker: celery -A eventful worker -l info --loglevel=DEBUG