from django.contrib import admin

from apps.stats.models import ActionLog


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'created_at', 'school')
    list_filter = ('action', 'school')
