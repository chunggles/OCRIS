"""
The production web server in the cloud container (see Dockerfile and backend/start.sh).

Reading one form takes 30 to 70 seconds and about 300 MB of memory (Python and Tesseract together),
and it runs inside the upload request. Two processes of four threads each answer up to eight
requests at once, so other people can keep working while forms are read. Uploads of one person run
one after another, so on a 2 GB instance several people can upload at the same time.
"""
import os

bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"
workers = int(os.getenv('WEB_WORKERS', '2'))
worker_class = 'gthread'
threads = int(os.getenv('WEB_THREADS', '4'))
timeout = int(os.getenv('WEB_TIMEOUT', '180'))   # longer than the slowest OCR, with others running
graceful_timeout = 85                            # lets a form being read finish when the server stops
                                                 # (Render waits 90: maxShutdownDelaySeconds in render.yaml)
max_requests = 500                               # a fresh process now and then keeps memory in check
max_requests_jitter = 50

errorlog = '-'
accesslog = '-'
# The path without the query string: searches carry pupils' names, which must not end up in the logs
access_log_format = '%(m)s %(U)s %(s)s %(B)s %(L)ss'
