import multiprocessing
import os

# Configuración básica
bind = "0.0.0.0:80"
workers = 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
backlog = 2048
graceful_timeout = 30

# Configuración de logs
accesslog = "/opt/hostberry/logs/access.log"
errorlog = "/opt/hostberry/logs/error.log"
loglevel = "info"

# Configuración de seguridad
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Configuración de procesos
preload_app = True
daemon = False
pidfile = "/opt/hostberry/gunicorn.pid"
umask = 0o022
user = "root"
group = "root"

# Configuración de SSL (descomentar si se usa HTTPS)
# keyfile = "/etc/hostberry/ssl/hostberry.key"
# certfile = "/etc/hostberry/ssl/hostberry.crt"

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_fork(server, worker):
    pass

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.info("worker received SIGABRT signal") 