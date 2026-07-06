from django.contrib import admin

from apps.gamification.models import (
    XPTransaction, Level, UserLevel, Achievement, UserAchievement,
    Streak, Challenge, ChallengeAttempt,
)


@admin.register(XPTransaction)
class XPTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'reason', 'created_at')
    list_filter = ('reason',)


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ('number', 'xp_required', 'bonus_percent')


@admin.register(UserLevel)
class UserLevelAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'total_xp')


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'icon_emoji')
    list_filter = ('category',)


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ('user', 'achievement', 'awarded_at')


@admin.register(Streak)
class StreakAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_streak', 'longest_streak', 'last_activity_date')


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ('grade_number', 'language', 'week_start', 'status')
    list_filter = ('status',)


@admin.register(ChallengeAttempt)
class ChallengeAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'challenge', 'score', 'is_completed')
