from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.loans.models import TextbookLoan, RegularBookLoan
from apps.gamification.models import UserLevel
from apps.schools.models import TransferLog


@transaction.atomic
def initiate_departure(user, initiated_by):
    if TransferLog.objects.filter(user=user, status__in=[TransferLog.Status.DEPARTING, TransferLog.Status.PENDING]).exists():
        return None, 'У пользователя уже есть активный запрос на перевод'
    active_textbook_loans = TextbookLoan.objects.filter(student=user, status=TextbookLoan.Status.ACTIVE)
    active_book_loans = RegularBookLoan.objects.filter(user=user, status=RegularBookLoan.Status.ACTIVE)
    if active_textbook_loans.exists() or active_book_loans.exists():
        return None, 'Не все книги и учебники сданы'

    user_level = UserLevel.objects.filter(user=user).first()
    xp_before = user_level.total_xp if user_level else 0

    transfer = TransferLog.objects.create(
        user=user,
        from_school=user.school,
        to_school=None,
        initiated_by=initiated_by,
        status=TransferLog.Status.DEPARTING,
        xp_before=xp_before,
    )

    user.transfer_status = 'departing'
    user.save()

    return transfer, None


@transaction.atomic
def complete_departure(user_id, initiated_by):
    transfer = TransferLog.objects.filter(
        user_id=user_id, status=TransferLog.Status.DEPARTING,
    ).first()
    if not transfer:
        return None, 'Нет активного запроса на уход'

    active_textbook_loans = TextbookLoan.objects.filter(student_id=user_id, status=TextbookLoan.Status.ACTIVE)
    active_book_loans = RegularBookLoan.objects.filter(user_id=user_id, status=RegularBookLoan.Status.ACTIVE)
    if active_textbook_loans.exists() or active_book_loans.exists():
        return None, 'Не все книги и учебники сданы'

    user = User.objects.get(id=user_id)
    user.school = None
    user.grade = None
    user.transfer_status = 'pending'
    user.save()

    transfer.status = TransferLog.Status.PENDING
    transfer.save()

    return transfer, None


@transaction.atomic
def accept_transfer(user_id, to_school, initiated_by):
    transfer = TransferLog.objects.filter(
        user_id=user_id, status=TransferLog.Status.PENDING,
    ).first()
    if not transfer:
        return None, 'Нет пользователя, ожидающего перевода'

    user = User.objects.get(id=user_id)
    old_school = transfer.from_school
    user.school = to_school
    user.transfer_status = 'completed'
    user.save()

    if user.role == User.Role.TEACHER:
        TextbookLoan.objects.filter(student=user, borrower_type='teacher', school=old_school).update(school=to_school)
        RegularBookLoan.objects.filter(user=user, school=old_school).update(school=to_school)

    user_level = UserLevel.objects.filter(user=user).first()
    if user_level:
        user_level.total_xp = int(user_level.total_xp * 0.5)
        user_level.save()
        from apps.gamification.services import update_user_level
        update_user_level(user_level)
        xp_after = user_level.total_xp
    else:
        xp_after = 0

    transfer.to_school = to_school
    transfer.status = TransferLog.Status.COMPLETED
    transfer.completed_at = timezone.now()
    transfer.xp_after = xp_after
    transfer.save()

    return transfer, None


@transaction.atomic
def cancel_transfer(user_id):
    transfer = TransferLog.objects.filter(
        user_id=user_id, status__in=[TransferLog.Status.DEPARTING, TransferLog.Status.PENDING],
    ).first()
    if not transfer:
        return None, 'Нет активного перевода'

    user = User.objects.get(id=user_id)
    if transfer.status == TransferLog.Status.PENDING and transfer.from_school:
        user.school = transfer.from_school
    user.transfer_status = ''
    user.save()

    transfer.status = TransferLog.Status.CANCELLED
    transfer.save()

    return transfer, None
