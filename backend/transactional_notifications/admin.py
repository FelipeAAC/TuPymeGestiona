from django.contrib import admin

from .models import TransactionalNotification, TransactionalNotificationAttempt

admin.site.register(TransactionalNotification)
admin.site.register(TransactionalNotificationAttempt)
