from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.accounts.views import login_view, logout_view, token_refresh_view, me_view
from apps.schools.views import DistrictViewSet, SchoolViewSet, ClassViewSet, TransferViewSet
from apps.catalog.views import CategoryViewSet, TextbookViewSet, TextbookStockViewSet, RegularBookViewSet
from apps.loans.views import TextbookLoanViewSet, RegularBookLoanViewSet
from apps.gamification.views import (
    XPTransactionViewSet, LevelViewSet, UserLevelViewSet,
    AchievementViewSet, UserAchievementViewSet, StreakViewSet,
    ChallengeViewSet, ChallengeAttemptViewSet,
)
from apps.notifications.views import NewsViewSet
from apps.stats.views import ActionLogViewSet

router = DefaultRouter()
router.register('districts', DistrictViewSet)
router.register('schools', SchoolViewSet)
router.register('classes', ClassViewSet)
router.register('transfers', TransferViewSet)
router.register('categories', CategoryViewSet)
router.register('textbooks', TextbookViewSet)
router.register('textbook-stocks', TextbookStockViewSet)
router.register('regular-books', RegularBookViewSet)
router.register('textbook-loans', TextbookLoanViewSet)
router.register('book-loans', RegularBookLoanViewSet)
router.register('xp-transactions', XPTransactionViewSet)
router.register('levels', LevelViewSet)
router.register('user-levels', UserLevelViewSet)
router.register('achievements', AchievementViewSet)
router.register('user-achievements', UserAchievementViewSet)
router.register('streaks', StreakViewSet)
router.register('challenges', ChallengeViewSet)
router.register('challenge-attempts', ChallengeAttemptViewSet)
router.register('news', NewsViewSet)
router.register('action-logs', ActionLogViewSet)

urlpatterns = [
    path('auth/login/', login_view, name='api_login'),
    path('auth/logout/', logout_view, name='api_logout'),
    path('auth/refresh/', token_refresh_view, name='api_refresh'),
    path('auth/me/', me_view, name='api_me'),
    path('', include(router.urls)),
]
