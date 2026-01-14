import os
import multiprocessing

# Bind to port from env or default
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Number of workers
workers = int(os.getenv("GUNICORN_WORKERS", min(multiprocessing.cpu_count() * 2 + 1, 4)))

# Worker class for async FastAPI
worker_class = "uvicorn.workers.UvicornWorker"

# Timeout for workers (increase for long downloads)
timeout = 300

# Graceful timeout
graceful_timeout = 120

# Keep alive
keepalive = 5

# Access log
accesslog = "-"
errorlog = "-"
loglevel = "info"
