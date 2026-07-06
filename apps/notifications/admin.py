from django.contrib import admin

from apps.notifications.models import News, Notification


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'author_level', 'school', 'is_published', 'published_at')
    list_filter = ('is_published', 'author_level', 'school')
    search_fields = ('title',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'message', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('message', 'user__login')
