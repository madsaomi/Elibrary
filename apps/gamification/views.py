from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from django.utils import timezone
from apps.gamification.models import (
    XPTransaction, Level, UserLevel, Achievement, UserAchievement,
    Streak, Challenge, ChallengeAttempt,
)
from apps.gamification.serializers import (
    XPTransactionSerializer, LevelSerializer, UserLevelSerializer,
    AchievementSerializer, UserAchievementSerializer, StreakSerializer,
    ChallengeSerializer, ChallengeAttemptSerializer,
)
from apps.gamification.services import add_xp, update_streak
from api.v1.permissions import IsSchoolAdminOrSuperAdmin


class XPTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = XPTransaction.objects.all()
    serializer_class = XPTransactionSerializer

    def get_queryset(self):
        return XPTransaction.objects.filter(user=self.request.user)


class LevelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Level.objects.all()
    serializer_class = LevelSerializer


class UserLevelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserLevel.objects.all()
    serializer_class = UserLevelSerializer

    def get_queryset(self):
        return UserLevel.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        qs = UserLevel.objects.filter(user__school=request.user.school).select_related('user', 'level').order_by('-total_xp')[:50]
        return Response(UserLevelSerializer(qs, many=True).data)


class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Achievement.objects.all()
    serializer_class = AchievementSerializer


class UserAchievementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserAchievement.objects.all()
    serializer_class = UserAchievementSerializer

    def get_queryset(self):
        return UserAchievement.objects.filter(user=self.request.user)


class StreakViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Streak.objects.all()
    serializer_class = StreakSerializer

    def get_queryset(self):
        return Streak.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def checkin(self, request):
        streak = update_streak(request.user)
        return Response(StreakSerializer(streak).data)


class ChallengeViewSet(viewsets.ModelViewSet):
    queryset = Challenge.objects.all()
    serializer_class = ChallengeSerializer
    permission_classes = [IsSchoolAdminOrSuperAdmin]

    def _check_moderator(self, request):
        if request.user.role not in ('school_admin', 'superadmin'):
            return Response({'error': 'Доступ запрещён'}, status=status.HTTP_403_FORBIDDEN)
        return None

    @action(detail=True, methods=['post'])
    def moderate(self, request, pk=None):
        err = self._check_moderator(request)
        if err: return err
        challenge = self.get_object()
        if challenge.status != Challenge.Status.DRAFT:
            return Response({'error': 'Челлендж не в статусе черновика'}, status=status.HTTP_400_BAD_REQUEST)
        questions = request.data.get('questions', challenge.questions)
        challenge.questions = questions
        challenge.status = Challenge.Status.PUBLISHED
        challenge.save()
        return Response(ChallengeSerializer(challenge).data)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        err = self._check_moderator(request)
        if err: return err
        challenge = self.get_object()
        if challenge.status != Challenge.Status.DRAFT:
            return Response({'error': 'Челлендж не в статусе черновика'}, status=status.HTTP_400_BAD_REQUEST)
        challenge.status = Challenge.Status.PUBLISHED
        challenge.save()
        return Response(ChallengeSerializer(challenge).data)

    @action(detail=False, methods=['get'])
    def pending_moderation(self, request):
        err = self._check_moderator(request)
        if err: return err
        qs = Challenge.objects.filter(status=Challenge.Status.DRAFT)
        if request.user.role == 'school_admin':
            qs = qs.filter(school=request.user.school)
        return Response(ChallengeSerializer(qs, many=True).data)


class ChallengeAttemptViewSet(viewsets.ModelViewSet):
    queryset = ChallengeAttempt.objects.all()
    serializer_class = ChallengeAttemptSerializer

    def get_queryset(self):
        return ChallengeAttempt.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def start(self, request):
        import random
        challenge_id = request.data.get('challenge_id')
        try:
            challenge = Challenge.objects.get(id=challenge_id)
        except Challenge.DoesNotExist:
            return Response({'error': 'Челлендж не найден'}, status=status.HTTP_404_NOT_FOUND)
        if challenge.status != Challenge.Status.PUBLISHED:
            return Response({'error': 'Челлендж ещё не опубликован'}, status=status.HTTP_400_BAD_REQUEST)
        if len(challenge.questions) != 15:
            return Response({'error': 'Челлендж должен содержать ровно 15 вопросов'}, status=status.HTTP_400_BAD_REQUEST)
        for i, q in enumerate(challenge.questions):
            if len(q.get('options', [])) != 3 or ('correct' not in q and 'correct_index' not in q):
                return Response({'error': f'Вопрос {i+1} должен иметь ровно 3 варианта ответа'}, status=status.HTTP_400_BAD_REQUEST)
        order = list(range(len(challenge.questions)))
        random.shuffle(order)
        attempt, created = ChallengeAttempt.objects.get_or_create(
            challenge=challenge, user=request.user,
            defaults={'question_order': order},
        )
        return Response(ChallengeAttemptSerializer(attempt).data)

    @action(detail=True, methods=['post'])
    def answer(self, request, pk=None):
        attempt = self.get_object()
        question_idx = request.data.get('question_idx')
        answer = request.data.get('answer')
        if attempt.is_completed:
            return Response({'error': 'Челлендж уже завершён'}, status=status.HTTP_400_BAD_REQUEST)
        attempt.answers[str(question_idx)] = answer
        attempt.save()
        return Response(ChallengeAttemptSerializer(attempt).data)

    @action(detail=True, methods=['post'])
    def finish(self, request, pk=None):
        attempt = self.get_object()
        if attempt.is_completed:
            return Response({'error': 'Уже завершён'}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        elapsed = (now - attempt.started_at).total_seconds() / 60
        if elapsed > attempt.time_limit_minutes:
            attempt.is_completed = True
            attempt.completed_at = now
            attempt.save()
            add_xp(request.user, 0, 'challenge', school=request.user.school)
            return Response(ChallengeAttemptSerializer(attempt).data)
        score = 0
        for idx, answer in attempt.answers.items():
            question = attempt.challenge.questions[int(idx)]
            correct = question.get('correct_index', question.get('correct', ''))
            if str(answer) == str(correct):
                score += 1
        attempt.score = score
        attempt.is_completed = True
        attempt.completed_at = now
        attempt.save()
        add_xp(request.user, score * 10, 'challenge', school=request.user.school)
        return Response(ChallengeAttemptSerializer(attempt).data)

    @action(detail=True, methods=['post'])
    def check_timeout(self, request, pk=None):
        attempt = self.get_object()
        if attempt.is_completed:
            return Response({'is_completed': True})
        now = timezone.now()
        elapsed = (now - attempt.started_at).total_seconds()
        time_left = attempt.time_limit_minutes * 60 - elapsed
        if time_left <= 0:
            return self.finish(request, pk=pk)
        return Response({
            'is_completed': False,
            'time_left_seconds': int(time_left),
            'started_at': attempt.started_at.isoformat(),
        })
