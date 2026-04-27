# gunicorn.conf.py — production config for dam-monitor

import multiprocessing

# Binding
bind = "0.0.0.0:80"

# Workers: 2 sync workers is enough for this app.
# Increase to 4 if you have ≥4 CPU cores.
workers = 2
worker_class = "sync"
worker_connections = 100
timeout = 60          # seconds — covers slow Open-Meteo fetches
keepalive = 5

# Load the model once before forking workers (avoids N re-trainings)
preload_app = True

# Logging
accesslog = "-"       # stdout
errorlog  = "-"       # stderr
loglevel  = "info"

# Process naming
proc_name = "dam-monitor"
