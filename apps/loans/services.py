import hashlib
import hmac
import json
import time
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from django.db.models import Q

from apps.catalog.models import TextbookStock, RegularBook, SubjectTextbook
from apps.loans.models import TextbookLoan, RegularBookLoan
from apps.accounts.models import User


def get_student_textbook_set(student):
    if not student.grade:
        return []
    assignments = SubjectTextbook.objects.filter(school_class=student.grade).select_related('textbook')
    assignment_textbook_ids = [a.textbook_id for a in assignments]

    active_loans = TextbookLoan.objects.filter(
        student=student, textbook_id__in=assignment_textbook_ids,
        status__in=[TextbookLoan.Status.ACTIVE, TextbookLoan.Status.OVERDUE],
    )
    loan_map = {loan.textbook_id: loan for loan in active_loans}

    stocks = TextbookStock.objects.filter(school=student.school, textbook_id__in=assignment_textbook_ids)
    stock_map = {stock.textbook_id: stock for stock in stocks}

    result = []
    for assignment in assignments:
        active_loan = loan_map.get(assignment.textbook_id)
        stock = stock_map.get(assignment.textbook_id)
        result.append({
            'assignment': assignment,
            'textbook': assignment.textbook,
            'stock': stock,
            'active_loan': active_loan,
            'status': _get_loan_status(active_loan, stock),
        })
    return result


def _get_loan_status(active_loan, stock):
    if active_loan:
        if active_loan.status == TextbookLoan.Status.OVERDUE:
            return 'overdue'
        return 'issued'
    if stock and stock.available_copies > 0:
        return 'available'
    return 'unavailable'


@transaction.atomic
def issue_textbooks_to_class(school, class_obj, issued_by):
    students = User.objects.filter(grade=class_obj, school=school, role=User.Role.STUDENT)
    assignments = SubjectTextbook.objects.filter(school_class=class_obj).select_related('textbook')
    all_loans = []
    stock_list = list(TextbookStock.objects.filter(
        school=school, textbook__in=[a.textbook for a in assignments]
    ).select_for_update())
    stock_map = {s.textbook_id: s for s in stock_list}
    existing_loans = set(TextbookLoan.objects.filter(
        student__in=students, textbook__in=[a.textbook for a in assignments],
        status=TextbookLoan.Status.ACTIVE,
    ).values_list('student_id', 'textbook_id'))
    for student in students:
        for assignment in assignments:
            stock = stock_map.get(assignment.textbook_id)
            if not stock or stock.available_copies < 1:
                continue
            if (student.id, assignment.textbook_id) in existing_loans:
                continue
            stock.available_copies -= 1
            stock.save()
            loan = TextbookLoan.objects.create(
                school=school, textbook=assignment.textbook,
                student=student, issued_by=issued_by,
                due_date=timezone.now().date() + timezone.timedelta(days=365),
            )
            all_loans.append(loan)
    return all_loans


def _hmac_secret():
    return settings.SECRET_KEY.encode('utf-8')


def generate_qr_token(payload: dict, ttl_seconds=120):
    now = int(time.time())
    token_payload = {**payload, 'iat': now, 'exp': now + ttl_seconds, 'jti': str(uuid.uuid4())}
    message = json.dumps(token_payload, separators=(',', ':'), sort_keys=True)
    signature = hmac.new(_hmac_secret(), message.encode('utf-8'), hashlib.sha256).hexdigest()
    return f'{message}.{signature}'


def validate_qr_token(token: str):
    try:
        dot = token.rfind('.')
        message, signature = token[:dot], token[dot + 1:]
        expected = hmac.new(_hmac_secret(), message.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(message)
        if time.time() > payload.get('exp', 0):
            return None
        return payload
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


@transaction.atomic
def issue_textbooks(school, student, textbook_ids, issued_by):
    from apps.catalog.models import TextbookStock
    from apps.loans.models import TextbookLoan
    from django.utils import timezone
    if not textbook_ids:
        return []
    stocks = list(TextbookStock.objects.filter(school=school, textbook_id__in=textbook_ids).select_for_update())
    stock_map = {str(s.textbook_id): s for s in stocks}
    loans = []
    for tb_id in textbook_ids:
        stock = stock_map.get(str(tb_id))
        if not stock or stock.available_copies < 1:
            continue
        existing = TextbookLoan.objects.filter(student=student, textbook_id=tb_id, status__in=[TextbookLoan.Status.ACTIVE, TextbookLoan.Status.OVERDUE]).exists()
        if existing:
            continue
        due = (timezone.now().date() + timezone.timedelta(days=7 if issued_by.role == User.Role.TEACHER else 365))
        loan = TextbookLoan.objects.create(
            textbook_id=tb_id, student=student, issued_by=issued_by,
            due_date=due, status=TextbookLoan.Status.ACTIVE,
            school=school, borrower_type='teacher' if issued_by.role == User.Role.TEACHER else 'student',
        )
        stock.available_copies -= 1
        stock.save()
        loans.append(loan)
    return loans


@transaction.atomic
def return_textbooks(loan_ids, returned_by, forced=False):
    from apps.gamification.services import add_xp, update_streak, award_comeback_bonus
    loans = TextbookLoan.objects.filter(id__in=loan_ids).select_related('textbook', 'student', 'school')
    stock_ids = [(loan.school_id, loan.textbook_id) for loan in loans]
    stocks = list(TextbookStock.objects.filter(school_id__in={s for s,_ in stock_ids}, textbook_id__in={t for _,t in stock_ids}).select_for_update())
    stock_map = {(s.school_id, s.textbook_id): s for s in stocks}
    for loan in loans:
        loan.status = TextbookLoan.Status.FORCED if forced else TextbookLoan.Status.RETURNED
        loan.returned_at = timezone.now()
        loan.save()
        stock = stock_map.get((loan.school_id, loan.textbook_id))
        if stock:
            stock.available_copies += 1
            stock.save()
        if not forced:
            if loan.due_date and loan.due_date < timezone.now().date():
                add_xp(loan.student, 15, 'return_late', school=loan.school)
            else:
                add_xp(loan.student, 30, 'return_ontime', school=loan.school)
                award_comeback_bonus(loan.student)
            update_streak(loan.student)
    return loans


@transaction.atomic
def issue_books(school, user, book_ids, issued_by):
    loans = []
    for bk_id in book_ids:
        book = RegularBook.objects.filter(school=school, id=bk_id).select_for_update().first()
        if not book or book.available_copies < 1:
            continue
        book.available_copies -= 1
        book.save()
        loan = RegularBookLoan.objects.create(
            school=school, book=book, user=user, issued_by=issued_by,
        )
        loans.append(loan)
    return loans


@transaction.atomic
def return_books(loan_ids, forced=False):
    from apps.gamification.services import add_xp, update_streak, award_comeback_bonus
    loans = RegularBookLoan.objects.filter(id__in=loan_ids).select_related('book', 'user', 'school')
    book_ids = [loan.book_id for loan in loans]
    books = list(RegularBook.objects.filter(id__in=book_ids).select_for_update())
    book_map = {b.id: b for b in books}
    for loan in loans:
        loan.status = RegularBookLoan.Status.FORCED if forced else RegularBookLoan.Status.RETURNED
        loan.returned_at = timezone.now()
        loan.save()
        book = book_map.get(loan.book_id)
        if book:
            book.available_copies += 1
            book.save()
        if not forced:
            if loan.due_date and loan.due_date < timezone.now().date():
                add_xp(loan.user, 15, 'return_late', school=loan.school)
            else:
                add_xp(loan.user, 30, 'return_ontime', school=loan.school)
                award_comeback_bonus(loan.user)
            update_streak(loan.user)
    return loans


def create_issue_token(school_id, user_id, item_ids, item_type='book'):
    payload = {
        'school_id': str(school_id),
        'user_id': str(user_id),
        'item_ids': [str(i) for i in item_ids],
        'item_type': item_type,
    }
    return generate_qr_token(payload)


def process_qr_issue(token, librarian):
    payload = validate_qr_token(token)
    if not payload:
        return None, 'Недействительный или просроченный QR-код'
    if str(librarian.school_id) != payload['school_id']:
        return None, 'QR-код относится к другой школе'
    user = User.objects.filter(id=payload['user_id']).first()
    if not user:
        return None, 'Пользователь не найден'
    item_type = payload['item_type']
    item_ids = payload['item_ids']
    if item_type == 'textbook':
        loans = issue_textbooks(librarian.school, user, item_ids, librarian)
    else:
        loans = issue_books(librarian.school, user, item_ids, librarian)
    return loans, None


def create_return_token(school_id, user_id, loan_ids, item_type='book'):
    payload = {
        'school_id': str(school_id),
        'user_id': str(user_id),
        'loan_ids': [str(i) for i in loan_ids],
        'item_type': item_type,
        'action': 'return',
    }
    return generate_qr_token(payload)


def process_qr_return(token, librarian):
    payload = validate_qr_token(token)
    if not payload:
        return None, 'Недействительный или просроченный QR-код'
    if str(librarian.school_id) != payload['school_id']:
        return None, 'QR-код относится к другой школе'
    if payload.get('action') != 'return':
        return None, 'Неверный тип QR-кода'
    item_type = payload['item_type']
    loan_ids = payload['loan_ids']
    if item_type == 'textbook':
        loans = return_textbooks(loan_ids, librarian)
    else:
        loans = return_books(loan_ids)
    return loans, None
