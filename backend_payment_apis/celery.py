# ----- 3rd Party Libraries -----
from __future__ import absolute_import, unicode_literals
from datetime import timedelta
import os
from celery import Celery
from celery.schedules import crontab
import logging
from celery.utils.log import get_task_logger

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_payment_apis.settings')

app = Celery('backend_payment_apis')

app.conf.beat_schedule = {
    'update-transaction-states-every-1-seconds': {
        'task': 'payments.tasks.update_transaction_states',
        'schedule': timedelta(seconds=1)  # every 3 seconds
    },
}

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.beat_scheduler = 'django_celery_beat.schedulers.DatabaseScheduler'

# # Configure worker settings
app.conf.worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
app.conf.worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
app.conf.worker_hijack_root_logger = False

logger = get_task_logger(__name__)
logger.setLevel(logging.WARNING)
logging.getLogger('django').setLevel(logging.WARNING)
logging.getLogger('celery').setLevel(logging.WARNING)

# # Retry settings for tasks
# app.conf.task_annotations = {
#     '*': {
#         'max_retries': 3,
#         'default_retry_delay': 5  # Retry after 1 minute
#     }
# }

# app.conf.task_routes = {
#     'payments.tasks.update_transaction_states': {'queue': 'high_priority'},
# }

# backend_payment_apis/celery.py

# from __future__ import absolute_import, unicode_literals
# import os
# from celery import Celery
# from datetime import timedelta
# import logging
# from celery.utils.log import get_task_logger

# # Set the default Django settings module for the 'celery' program.
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_payment_apis.settings')

# # Initialize Celery app
# app = Celery('backend_payment_apis')

# # Using a string here means the worker doesn't have to serialize the configuration object to child processes.
# app.config_from_object('django.conf:settings', namespace='CELERY')

# # Load task modules from all registered Django app configs.
# app.autodiscover_tasks()

# # Configure Redis as the broker and enable broker retry on startup
# app.conf.broker_url = 'redis://redis:6379/0'
# app.conf.broker_connection_retry_on_startup = True

# # Use Django Database Scheduler for Celery Beat
# app.conf.beat_scheduler = 'django_celery_beat.schedulers.DatabaseScheduler'

# # Configure periodic task schedule
# app.conf.beat_schedule = {
#     'update-transaction-states-every-5-seconds': {
#         'task': 'payments.tasks.update_transaction_states',
#         'schedule': timedelta(seconds=5)  # every 5 minutes
#     },
# }

# # Set timezone
# app.conf.timezone = 'UTC'

# # Configure worker settings
# app.conf.worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
# app.conf.worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
# app.conf.worker_hijack_root_logger = False

# # Configure logging
# logger = get_task_logger(__name__)
# logger.setLevel(logging.WARNING)
# logging.getLogger('django').setLevel(logging.WARNING)
# logging.getLogger('celery').setLevel(logging.WARNING)

# # Retry settings for tasks
# app.conf.task_annotations = {
#     '*': {
#         'max_retries': 3,
#         'default_retry_delay': 60  # Retry after 1 minute
#     }
# }

# Queue configuration for task priority
# app.conf.task_routes = {
#     'payments.tasks.update_transaction_states': {'queue': 'high_priority'},
# }