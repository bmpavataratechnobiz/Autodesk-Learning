import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab


os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'Autodesk_Project.settings'
)

app = Celery('Autodesk_Project')

app.config_from_object(
    'django.conf:settings',
    namespace='CELERY'
)

app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print('Request:{0!r}'.format(self.request))


# app.conf.beat_schedule = {
#     'deactivate_expired_subscriptions' : {
#         'task':'aps_api.tasks.deactivate_expired_subscriptions',
#         'schedule':crontab(minute='*/30')
#     },
# }

