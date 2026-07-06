from rest_framework import serializers

from apps.gamification.models import (
    XPTransaction, Level, UserLevel, Achievement, UserAchievement,
    Streak, Challenge, ChallengeAttempt,
)


class XPTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = XPTransaction
        fields = '__all__'
        read_only_fields = ['user', 'school']


class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = '__all__'


class UserLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserLevel
        fields = '__all__'
        read_only_fields = ['user', 'level', 'total_xp']


class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = '__all__'


class UserAchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAchievement
        fields = '__all__'
        read_only_fields = ['user', 'achievement']


class StreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = Streak
        fields = '__all__'
        read_only_fields = ['user', 'school', 'current_streak', 'longest_streak']


class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = '__all__'
        read_only_fields = ['school', 'status']


class ChallengeAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChallengeAttempt
        fields = '__all__'
        read_only_fields = ['user', 'challenge', 'started_at', 'score', 'is_completed']
