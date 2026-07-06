from django.db.models import Count, Sum, Avg

from apps.accounts.models import User
from apps.catalog.models import TextbookStock, RegularBook
from apps.loans.models import TextbookLoan, RegularBookLoan
from apps.gamification.models import UserLevel, XPTransaction


def get_school_stats(school):
    students = User.objects.filter(school=school, role=User.Role.STUDENT).count()
    teachers = User.objects.filter(school=school, role=User.Role.TEACHER).count()
    textbook_stocks = TextbookStock.objects.filter(school=school).aggregate(
        total=Sum('total_copies'), available=Sum('available_copies'),
    )
    regular_books = RegularBook.objects.filter(school=school).aggregate(
        total=Sum('total_copies'), available=Sum('available_copies'),
    )
    active_loans = TextbookLoan.objects.filter(school=school, status=TextbookLoan.Status.ACTIVE).count()
    active_book_loans = RegularBookLoan.objects.filter(school=school, status=RegularBookLoan.Status.ACTIVE).count()
    total_xp = UserLevel.objects.filter(user__school=school).aggregate(total=Sum('total_xp'))['total'] or 0
    avg_xp = total_xp / students if students else 0

    return {
        'students': students,
        'teachers': teachers,
        'textbook_stocks': textbook_stocks,
        'regular_books': regular_books,
        'active_loans': active_loans + active_book_loans,
        'total_xp': total_xp,
        'avg_xp': round(avg_xp, 1),
    }
