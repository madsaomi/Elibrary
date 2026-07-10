import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Avg
from django.contrib.sessions.models import Session
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.translation import gettext as _
from datetime import date

from apps.accounts.models import User
from apps.accounts.services import create_user, reset_password, activate_grade_access
from apps.catalog.models import Textbook, RegularBook, Category, SubjectTextbook, TextbookStock
from apps.loans.models import TextbookLoan, RegularBookLoan
from apps.loans.services import (
    create_issue_token, process_qr_issue, issue_textbooks, return_textbooks,
    issue_books, return_books, get_student_textbook_set,
    issue_textbooks_to_class, create_return_token, process_qr_return,
)
from apps.schools.models import Class  # noqa: F401 (used in users_list grouping)
from apps.gamification.models import UserLevel, Challenge, ChallengeAttempt
from apps.gamification.services import award_freeze_days
from apps.notifications.models import News
from apps.notifications.services import NewsService
from apps.schools.models import School, District
from apps.stats.models import ActionLog
from apps.core.services import export_to_excel, generate_return_list_excel
from dashboard.services import get_school_stats


@login_required
def home(request):
    stats = {}
    news = []
    leaderboard = []
    user_rank = None
    user_entry = None
    if request.user.role == 'superadmin':
        schools_count = School.objects.count()
        districts_count = District.objects.count()
        total_students = User.objects.filter(role=User.Role.STUDENT).count()
    elif request.user.school:
        stats = get_school_stats(request.user.school)
        news = NewsService.visible_to(request.user)[:5]
        full_lb = list(UserLevel.objects.filter(
            user__school=request.user.school,
        ).select_related('user', 'level').order_by('-total_xp'))
        leaderboard = full_lb[:10]
        current = next((ul for ul in full_lb if ul.user_id == request.user.id), None)
        if current:
            user_rank = full_lb.index(current) + 1
            if user_rank > 10:
                user_entry = current
    return render(request, 'dashboard/home.html', {
        'stats': stats,
        'news': news,
        'leaderboard': leaderboard,
        'user_rank': user_rank,
        'user_entry': user_entry,
    })


@login_required
def profile(request):
    from apps.gamification.models import Achievement as AchModel
    streak = getattr(request.user, 'streak', None)
    level_info = getattr(request.user, 'level_info', None)
    ctx = {'streak': streak, 'level_info': level_info}
    if request.user.role == 'student':
        achievements = request.user.achievements.select_related('achievement').all()
        ctx['earned_ids'] = set(ua.achievement_id for ua in achievements)
        ctx['all_achievements'] = AchModel.objects.all()
    return render(request, 'dashboard/profile.html', ctx)


@login_required
@require_POST
def award_freeze_view(request, user_id):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    target = User.objects.get(id=user_id)
    if target.school != request.user.school:
        return render(request, 'dashboard/error.html', {'error': _('Пользователь из другой школы')})
    days = int(request.POST.get('days', 1))
    award_freeze_days(target, days)
    return redirect('dashboard:profile')


@login_required
def users_list(request):
    if request.user.role not in ('superadmin', 'school_admin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})

    base = User.objects.select_related('grade', 'school').all()
    if request.user.role == 'school_admin':
        base = base.filter(school=request.user.school)
    elif request.user.role == 'superadmin':
        base = base.filter(role=User.Role.SCHOOL_ADMIN)

    q = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    grade_filter = request.GET.get('grade', '').strip()
    sort = request.GET.get('sort', 'name')

    if q:
        base = base.filter(Q(login__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    if role_filter:
        base = base.filter(role=role_filter)
    if grade_filter:
        base = base.filter(grade__number=grade_filter)

    if sort == 'name':
        base = base.order_by('last_name', 'first_name')
    elif sort == 'login':
        base = base.order_by('login')
    elif sort == 'role':
        base = base.order_by('role', 'last_name')
    else:
        base = base.order_by('last_name', 'first_name')

    # Статистика
    stats = base.aggregate(
        total=Count('id'),
        students=Count('id', filter=Q(role='student')),
        teachers=Count('id', filter=Q(role='teacher')),
        admins=Count('id', filter=Q(role__in=['school_admin', 'superadmin'])),
        active=Count('id', filter=Q(is_active=True)),
    )

    classes = (
        Class.objects.filter(school=request.user.school if request.user.role == 'school_admin' else None)
        .order_by('number', 'parallel')
    ) if request.user.role == 'school_admin' else (
        Class.objects.filter(school__in=base.values('school')).distinct().order_by('number', 'parallel')
    )

    # Группировка учеников по классам
    students_by_class = {}
    student_qs = base.filter(role='student').select_related('grade', 'school')
    for s in student_qs:
        key = f"{s.grade.number}{s.grade.parallel}" if s.grade else "—"
        students_by_class.setdefault(key, []).append(s)

    others = base.exclude(role='student').select_related('school')

    paginator = Paginator(base, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'dashboard/users/list.html', {
        'users': page_obj,
        'stats': stats,
        'classes': classes,
        'students_by_class': dict(sorted(students_by_class.items())),
        'others': others,
        'q': q,
        'role_filter': role_filter,
        'grade_filter': grade_filter,
        'sort': sort,
    })


@login_required
def reset_password_view(request, user_id):
    if request.user.role not in ('superadmin', 'school_admin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    target = User.objects.get(id=user_id)
    if request.user.role == 'school_admin' and target.school != request.user.school:
        return render(request, 'dashboard/error.html', {'error': _('Пользователь из другой школы')})
    if request.method == 'POST':
        new_password = reset_password(target)
        Session.objects.filter(user=target).delete()
        if target.role == 'school_admin':
            headers = ['Школа', 'Логин', 'Новый пароль']
            rows = [[target.school.name, target.login, new_password]]
        else:
            headers = ['ФИО', 'Новый пароль']
            rows = [[f'{target.last_name} {target.first_name}', new_password]]
        return export_to_excel(
            headers=headers, rows=rows,
            filename=f'password_reset_{target.login}.xlsx',
        )
    return render(request, 'dashboard/users/reset_password.html', {'target': target})


@login_required
def textbooks_list(request):
    PAGE_SIZE = 50
    textbooks = Textbook.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        textbooks = textbooks.filter(Q(title__icontains=q) | Q(subject__icontains=q) | Q(author__icontains=q))
    page = request.GET.get('page', 1)
    paginator = Paginator(textbooks, PAGE_SIZE)
    page_obj = paginator.get_page(page)
    return render(request, 'dashboard/textbooks/list.html', {'page_obj': page_obj, 'q': q})


@login_required
def textbook_create(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        subject = request.POST.get('subject', '').strip()
        grade_number = request.POST.get('grade_number', '').strip()
        language = request.POST.get('language', '')
        academic_year = request.POST.get('academic_year', '').strip()
        cover = request.FILES.get('cover')
        if title and subject and grade_number:
            tb = Textbook(title=title, subject=subject, grade_number=int(grade_number), language=language, academic_year=academic_year, cover=cover)
            tb.save()
            if request.user.role == 'school_admin':
                TextbookStock.objects.get_or_create(school=request.user.school, textbook=tb, defaults={'total_copies': 0, 'available_copies': 0})
            return redirect('dashboard:textbooks')
    return render(request, 'dashboard/textbooks/create.html', {'years': range(2020, 2031)})


@login_required
def textbook_stock_view(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    school = request.user.school
    stocks = TextbookStock.objects.filter(school=school).select_related('textbook')
    if request.method == 'POST':
        textbook_id = request.POST.get('textbook_id')
        total = int(request.POST.get('total_copies', 0))
        stock, _ = TextbookStock.objects.get_or_create(school=school, textbook_id=textbook_id)
        added = total - stock.total_copies
        stock.total_copies = total
        stock.available_copies = max(0, stock.available_copies + added)
        stock.save()
        return redirect('dashboard:textbook_stock')
    textbooks = Textbook.objects.all()
    return render(request, 'dashboard/textbooks/stock.html', {
        'stocks': stocks, 'textbooks': textbooks,
    })


@login_required
def books_list(request):
    PAGE_SIZE = 50
    books = RegularBook.objects.all()
    if request.user.role == 'school_admin':
        books = books.filter(school=request.user.school)
    q = request.GET.get('q', '').strip()
    if q:
        books = books.filter(Q(title__icontains=q) | Q(author__icontains=q))
    page = request.GET.get('page', 1)
    paginator = Paginator(books, PAGE_SIZE)
    page_obj = paginator.get_page(page)
    return render(request, 'dashboard/books/list.html', {'page_obj': page_obj, 'q': q})


@login_required
def book_create(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    school = request.user.school
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        author = request.POST.get('author', '').strip()
        total_copies = int(request.POST.get('total_copies', 1))
        category_id = request.POST.get('category_id')
        cover = request.FILES.get('cover')
        if title:
            RegularBook.objects.create(
                school=school, title=title, author=author or None,
                total_copies=total_copies, available_copies=total_copies,
                category_id=category_id or None, cover=cover,
            )
            return redirect('dashboard:books')
    categories = Category.objects.all()
    return render(request, 'dashboard/books/create.html', {'categories': categories})


@login_required
def bulk_issue_to_class(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    classes = Class.objects.filter(school=request.user.school, status=Class.Status.ACTIVE)
    if request.method == 'POST':
        class_id = request.POST.get('class_id')
        cls = Class.objects.get(id=class_id)
        loans = issue_textbooks_to_class(request.user.school, cls, request.user)
        ActionLog.objects.create(
            school=request.user.school, user=request.user,
            action=ActionLog.ActionType.LOAN,
            details={'class_id': str(class_id), 'count': len(loans)},
        )
        return redirect('dashboard:issue_textbooks')
    return render(request, 'dashboard/loans/bulk_issue.html', {'classes': classes})


@login_required
def export_students(request):
    if request.user.role not in ('superadmin', 'school_admin'):
        return HttpResponse(_('Доступ запрещён'), status=403)
    school = request.user.school
    users = User.objects.filter(school=school, role=User.Role.STUDENT).select_related('grade')
    rows = [[f'{u.last_name} {u.first_name}', str(u.grade) if u.grade else '', u.login] for u in users]
    return export_to_excel(
        headers=['ФИО', 'Класс', 'Логин'],
        rows=rows,
        filename='students.xlsx',
    )


@login_required
def qr_scanner(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    return render(request, 'dashboard/qr/scanner.html')


@login_required
def cart(request):
    book_ids = request.GET.getlist('book_id')
    books = RegularBook.objects.filter(id__in=book_ids) if book_ids else []
    return render(request, 'dashboard/qr/cart.html', {'books': books, 'book_ids': book_ids})


@login_required
def issue_textbooks_view(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    student_id = request.GET.get('student_id')
    if student_id:
        return redirect('dashboard:issue_textbooks_set', student_id=student_id)
    students = User.objects.filter(school=request.user.school, role=User.Role.STUDENT).select_related('grade')
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        textbook_ids = request.POST.getlist('textbook_ids')
        student = User.objects.get(id=student_id)
        loans = issue_textbooks(request.user.school, student, textbook_ids, request.user, 'student')
        ActionLog.objects.create(
            school=request.user.school, user=request.user,
            action=ActionLog.ActionType.LOAN,
            details={'student_id': str(student_id), 'count': len(loans)},
        )
        return redirect('dashboard:issue_textbooks')
    return render(request, 'dashboard/loans/issue_textbooks.html', {
        'students': students,
    })


@login_required
def class_add_student(request, class_id):
    if request.user.role not in ('superadmin', 'school_admin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    cls = Class.objects.select_related('school').get(id=class_id)
    school = cls.school
    if request.user.role == 'school_admin' and request.user.school != school:
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    if request.method == 'POST':
        from django.contrib import messages
        login_val = request.POST.get('login', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        if login_val:
            user = User.objects.filter(login=login_val).first()
            if user:
                user.grade = cls
                user.school = school
                user.save(update_fields=['grade', 'school'])
                messages.success(request, f'{user.get_full_name()} добавлен(а) в {cls.number}{cls.parallel}')
        elif first_name and last_name:
            user = User.objects.create(
                login=f'{first_name.lower()}.{last_name.lower()}_{cls.number}{cls.parallel}',
                first_name=first_name, last_name=last_name,
                role='student', grade=cls, school=school,
            )
            messages.success(request, f'{user.get_full_name()} создан(а) и добавлен(а) в {cls.number}{cls.parallel}')
        else:
            messages.error(request, _('Укажите логин существующего ученика или имя+фамилию нового'))
    return redirect('dashboard:manage_classes')


@login_required
def class_remove_student(request, class_id):
    if request.user.role not in ('superadmin', 'school_admin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    cls = Class.objects.select_related('school').get(id=class_id)
    if request.user.role == 'school_admin' and request.user.school != cls.school:
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    if request.method == 'POST':
        from django.contrib import messages
        student_id = request.POST.get('student_id')
        user = User.objects.filter(id=student_id, grade=cls, role='student').first()
        if user:
            user.grade = None
            user.save(update_fields=['grade'])
            messages.info(request, f'{user.get_full_name()} удалён(а) из {cls.number}{cls.parallel}')
        else:
            messages.error(request, _('Ученик не найден в этом классе'))
    return redirect('dashboard:manage_classes')


@login_required
def class_transfer_student(request, class_id):
    if request.user.role not in ('superadmin', 'school_admin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from_cls = Class.objects.select_related('school').get(id=class_id)
    if request.user.role == 'school_admin' and request.user.school != from_cls.school:
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    if request.method == 'POST':
        from django.contrib import messages
        student_id = request.POST.get('student_id')
        to_class_id = request.POST.get('to_class_id')
        user = User.objects.filter(id=student_id, grade=from_cls, role='student', school=from_cls.school).first()
        to_cls = Class.objects.filter(id=to_class_id, school=from_cls.school).first()
        if user and to_cls:
            user.grade = to_cls
            user.save(update_fields=['grade'])
            messages.success(request,
                f'{user.get_full_name()} переведён(а) из {from_cls.number}{from_cls.parallel} в {to_cls.number}{to_cls.parallel}')
        else:
            messages.error(request, _('Ошибка перевода: ученик или целевой класс не найден'))
    return redirect('dashboard:manage_classes')


@login_required
def issue_textbooks_set_view(request, student_id):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from django.shortcuts import get_object_or_404
    student = get_object_or_404(User, id=student_id)
    textbook_set = get_student_textbook_set(student)
    if request.method == 'POST':
        textbook_ids = request.POST.getlist('textbook_ids')
        loans = issue_textbooks(request.user.school, student, textbook_ids, request.user, 'student')
        return redirect('dashboard:issue_textbooks_set', student_id=student_id)
    else:
        return render(request, 'dashboard/loans/issue_set.html', {
            'student': student,
            'textbook_set': textbook_set,
        })


@login_required
def return_textbooks_view(request, student_id):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    student = User.objects.get(id=student_id)
    active_loans = TextbookLoan.objects.filter(student=student, status=TextbookLoan.Status.ACTIVE).select_related('textbook')
    if request.method == 'POST':
        loan_ids = request.POST.getlist('loan_ids')
        forced = request.POST.get('forced') == '1'
        loans = return_textbooks(loan_ids, request.user, forced)
        ActionLog.objects.create(
            school=request.user.school, user=request.user,
            action=ActionLog.ActionType.FORCED_RETURN if forced else ActionLog.ActionType.RETURN,
            details={'student_id': str(student_id), 'count': len(loans)},
        )
        return redirect('dashboard:users')
    return render(request, 'dashboard/loans/return_textbooks.html', {
        'student': student,
        'active_loans': active_loans,
    })


@login_required
def teacher_borrow_textbook(request):
    if request.user.role not in ('teacher', 'school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    user = request.user
    textbooks = Textbook.objects.all()
    show_all = request.GET.get('show_all') == '1' or request.POST.get('show_all') == '1'
    if user.role == 'teacher' and user.subject and not show_all:
        textbooks = textbooks.filter(subject__iexact=user.subject)
    if request.method == 'POST':
        textbook_ids = request.POST.getlist('textbook_ids')
        teacher = request.user
        if request.user.role == 'school_admin':
            teacher_id = request.POST.get('teacher_id')
            teacher = User.objects.get(id=teacher_id)
        loans = issue_textbooks(user.school, teacher, textbook_ids, request.user, 'teacher')
        return redirect('dashboard:my_loans')
    teachers = User.objects.filter(school=user.school, role=User.Role.TEACHER) if user.role == 'school_admin' else []
    PAGE_SIZE = 50
    page = request.GET.get('page', 1)
    paginator = Paginator(textbooks, PAGE_SIZE)
    page_obj = paginator.get_page(page)
    return render(request, 'dashboard/loans/teacher_borrow.html', {
        'page_obj': page_obj,
        'teachers': teachers,
        'show_all': show_all,
    })


@login_required
def qr_return_view(request):
    book_loans = RegularBookLoan.objects.filter(user=request.user, status=RegularBookLoan.Status.ACTIVE).select_related('book')
    if request.method == 'POST':
        loan_ids = request.POST.getlist('loan_ids')
        token = create_issue_token(request.user.school_id, str(request.user.id), loan_ids, 'book')
        return render(request, 'dashboard/qr/return_qr.html', {
            'token': token,
            'selected_count': len(loan_ids),
        })
    return render(request, 'dashboard/qr/select_return.html', {
        'book_loans': book_loans,
    })


@login_required
def activate_grade_5_view(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    if request.method == 'POST':
        grade_number = int(request.POST.get('grade_number', 5))
        academic_year = request.POST.get('academic_year', '')
        results = activate_grade_access(request.user.school, grade_number, academic_year)
        rows = [[r['student'].last_name + ' ' + r['student'].first_name, str(r['student'].grade), r['student'].login, r['password'] or '(уже есть)'] for r in results]
        return export_to_excel(
            headers=['ФИО', 'Класс', 'Логин', 'Пароль'],
            rows=rows,
            filename=f'grade_{grade_number}_activation.xlsx',
        )
    return render(request, 'dashboard/users/activate_grade.html')


@login_required
def inventory(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    stats = get_school_stats(request.user.school) if request.user.school else {}
    overdue_loans = TextbookLoan.objects.filter(
        Q(status=TextbookLoan.Status.ACTIVE) & Q(due_date__lt=date.today()),
    ).select_related('student', 'textbook')
    if request.user.role == 'school_admin':
        overdue_loans = overdue_loans.filter(school=request.user.school)
    return render(request, 'dashboard/stats/inventory.html', {
        'stats': stats,
        'overdue_loans': overdue_loans,
    })


@login_required
def superadmin_dashboard(request):
    if request.user.role != 'superadmin':
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    districts = District.objects.annotate(school_count=Count('schools'))
    schools = School.objects.select_related('district').annotate(
        student_count=Count('user', filter=Q(user__role=User.Role.STUDENT)),
    ).order_by('name')
    total_students = User.objects.filter(role=User.Role.STUDENT).count()
    schools_ranking = School.objects.annotate(
        avg_xp=Avg('user__level_info__total_xp'),
        student_count=Count('user', filter=Q(user__role=User.Role.STUDENT)),
    ).order_by('-avg_xp')
    return render(request, 'dashboard/stats/superadmin.html', {
        'districts': districts,
        'schools': schools,
        'schools_ranking': schools_ranking,
        'total_students': total_students,
    })


@login_required
def challenge_moderation(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    pending = Challenge.objects.filter(status=Challenge.Status.DRAFT)
    if request.user.role == 'school_admin':
        pending = pending.filter(Q(school=request.user.school) | Q(school__isnull=True))
    return render(request, 'dashboard/challenges/moderation.html', {'challenges': pending})


@login_required
def textbook_qr_return_view(request):
    user = request.user
    if request.user.role == 'student':
        textbook_loans = TextbookLoan.objects.filter(student=user, status=TextbookLoan.Status.ACTIVE).select_related('textbook')
    elif request.user.role in ('teacher', 'school_admin', 'superadmin'):
        textbook_loans = TextbookLoan.objects.filter(student=user, status=TextbookLoan.Status.ACTIVE, borrower_type='teacher').select_related('textbook')
    else:
        textbook_loans = []
    if request.method == 'POST':
        loan_ids = request.POST.getlist('loan_ids')
        token = create_return_token(user.school_id, str(user.id), loan_ids, 'textbook')
        return render(request, 'dashboard/qr/return_qr.html', {
            'token': token,
            'selected_count': len(loan_ids),
        })
    return render(request, 'dashboard/qr/textbook_select_return.html', {
        'textbook_loans': textbook_loans,
    })


@login_required
def return_list_export(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    school = request.user.school
    students = User.objects.filter(school=school, role=User.Role.STUDENT, grade__isnull=False).select_related('grade')
    debtors_only = request.GET.get('debtors') == '1'
    students_data = []
    assignments_by_class = {}
    all_student_ids = [s.id for s in students]
    all_textbook_ids = set()
    for student in students:
        cls = student.grade
        if cls.id not in assignments_by_class:
            assignments_by_class[cls.id] = list(
                SubjectTextbook.objects.filter(school_class=cls).select_related('textbook')
            )
        all_textbook_ids.update(a.textbook_id for a in assignments_by_class[cls.id])
    loans_by_key = {}
    all_loans = TextbookLoan.objects.filter(
        student_id__in=all_student_ids,
        textbook_id__in=all_textbook_ids,
    ).select_related('textbook').order_by('-created_at')
    for loan in all_loans:
        key = (loan.student_id, loan.textbook_id)
        if key not in loans_by_key:
            loans_by_key[key] = loan
    for student in students:
        cls = student.grade
        assignments = assignments_by_class[cls.id]
        subjects = []
        all_returned = True
        for assignment in assignments:
            loan = loans_by_key.get((student.id, assignment.textbook_id))
            status = 'returned' if (not loan or loan.status == TextbookLoan.Status.RETURNED) else 'active'
            if status == 'active':
                all_returned = False
            subjects.append({'name': assignment.textbook.subject, 'status': status})
        class_lang = student.grade.language or 'ru'
        students_data.append({
            'fio': f'{student.last_name} {student.first_name}',
            'total': len(subjects),
            'subjects': subjects,
            'all_returned': all_returned,
            'language': class_lang,
        })
    return generate_return_list_excel(students_data, debtors_only=debtors_only)


@login_required
def teacher_books_view(request):
    if request.user.role not in ('teacher', 'school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    user = request.user
    books = RegularBook.objects.filter(school=user.school)
    if request.method == 'POST':
        book_ids = request.POST.getlist('book_ids')
        borrower = user
        if request.user.role == 'school_admin':
            teacher_id = request.POST.get('teacher_id')
            borrower = User.objects.get(id=teacher_id)
        loans = issue_books(user.school, borrower, book_ids, request.user)
        return redirect('dashboard:my_loans')
    teachers = User.objects.filter(school=user.school, role=User.Role.TEACHER) if user.role == 'school_admin' else []
    PAGE_SIZE = 50
    page = request.GET.get('page', 1)
    paginator = Paginator(books, PAGE_SIZE)
    page_obj = paginator.get_page(page)
    return render(request, 'dashboard/loans/teacher_books.html', {
        'page_obj': page_obj,
        'teachers': teachers,
    })


@login_required
def challenge_moderation_detail(request, challenge_id):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    challenge = Challenge.objects.get(id=challenge_id)
    if request.method == 'POST':
        import json as _json
        questions_raw = request.POST.get('questions')
        if questions_raw:
            challenge.questions = _json.loads(questions_raw)
        action = request.POST.get('action')
        if action == 'publish':
            challenge.status = Challenge.Status.PUBLISHED
        challenge.save()
        return redirect('dashboard:challenge_moderation')
    return render(request, 'dashboard/challenges/moderation_detail.html', {
        'challenge': challenge,
    })


@login_required
def import_teachers_csv(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    if request.method == 'POST':
        import csv, io
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            return render(request, 'dashboard/users/import_teachers.html', {'error': 'Файл не загружен'})
        decoded = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        results = []
        for row in reader:
            first_name = row.get('ФИО', '').strip().split()[0] if row.get('ФИО') else ''
            last_name = ' '.join(row.get('ФИО', '').strip().split()[1:]) if row.get('ФИО') else ''
            subject = row.get('Предмет', '').strip()
            user, password = create_user(
                role=User.Role.TEACHER,
                first_name=first_name,
                last_name=last_name,
                school=request.user.school,
                subject=subject,
            )
            results.append({'user': user, 'password': password})
        rows = [[r['user'].last_name + ' ' + r['user'].first_name, r['user'].subject, r['user'].login, r['password']] for r in results]
        return export_to_excel(
            headers=['ФИО', 'Предмет', 'Логин', 'Пароль'],
            rows=rows,
            filename='import_teachers_result.xlsx',
        )
    return render(request, 'dashboard/users/import_teachers.html')


@login_required
def manage_districts(request):
    return redirect('dashboard:manage_schools')


@login_required
def manage_schools(request):
    if request.user.role != 'superadmin':
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    districts = District.objects.all()
    error = None
    if request.method == 'POST':
        action = request.POST.get('action', 'create')
        if action == 'district':
            name = request.POST.get('name', '').strip()
            if name:
                District.objects.get_or_create(name=name)
            return redirect('dashboard:manage_schools')
        name = request.POST.get('name', '').strip()
        district_id = request.POST.get('district_id')
        if not name:
            error = 'Название школы не может быть пустым'
        elif not district_id:
            error = 'Выберите район'
        else:
            try:
                district = District.objects.get(id=district_id)
            except (District.DoesNotExist, ValueError):
                error = 'Район не найден'
            else:
                school, created = School.objects.get_or_create(name=name, district=district)
                if created:
                    from apps.accounts.services import generate_password as gen_pwd, generate_login
                    admin_login = generate_login('admin', name.replace(' ', '_').lower(), school.id)
                    admin_pwd = gen_pwd()
                    User.objects.create_user(login=admin_login, password=admin_pwd, school=school, role='school_admin')
                    from apps.core.services import generate_school_admin_excel
                    return generate_school_admin_excel(school, admin_login, admin_pwd)
                else:
                    error = 'Школа с таким названием уже существует в этом районе'
    schools = School.objects.select_related('district').annotate(
        student_count=Count('user', filter=Q(user__role=User.Role.STUDENT)),
    ).order_by('district__name', 'name')
    return render(request, 'dashboard/schools/schools.html', {'schools': schools, 'districts': districts, 'error': error})


@login_required
def manage_classes(request):
    if request.user.role != 'school_admin':
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    school = request.user.school
    if request.method == 'POST':
        number = int(request.POST.get('number'))
        parallel = request.POST.get('parallel', '').strip()
        language = request.POST.get('language', 'ru')
        academic_year = request.POST.get('academic_year', '')
        s = school
        Class.objects.get_or_create(
            number=number, parallel=parallel, language=language,
            academic_year=academic_year, school=s,
        )
        return redirect('dashboard:manage_classes')
    classes = Class.objects.select_related('school')
    if school:
        classes = classes.filter(school=school)

    # Группировка учеников по классам
    students_by_class = {}
    if school:
        students_qs = User.objects.filter(school=school, role='student').select_related('grade').only('id', 'first_name', 'last_name', 'login', 'grade')

    for s in students_qs:
        if s.grade_id:
            students_by_class.setdefault(str(s.grade_id), []).append(s)

    # Данные для вкладки "Переводы"
    from apps.schools.models import TransferLog, PromotionLog
    outgoing = incoming = completed = []
    young_students = []
    current_year = next_year = ''
    promotions = []

    if school:
        # переводы
        outgoing = TransferLog.objects.filter(from_school=school).exclude(
            status=TransferLog.Status.COMPLETED
        ).select_related('user')
        incoming = TransferLog.objects.filter(
            status=TransferLog.Status.PENDING
        ).exclude(from_school=school).select_related('user', 'from_school')
        completed = TransferLog.objects.filter(
            Q(from_school=school) | Q(to_school=school),
            status=TransferLog.Status.COMPLETED,
        ).select_related('user', 'from_school', 'to_school').order_by('-completed_at')[:20]
        # продвижение
        promotions = PromotionLog.objects.filter(school=school).order_by('-created_at')[:10]
        current_year = str(timezone.now().year - 1) + '-' + str(timezone.now().year)
        next_year = str(timezone.now().year) + '-' + str(timezone.now().year + 1)
        # младшие классы
        young_classes = Class.objects.filter(school=school, number__lte=4, status=Class.Status.ACTIVE)
        young_students = User.objects.filter(
            school=school, role=User.Role.STUDENT,
            grade__in=young_classes, is_active_for_gamification=False,
        ).select_related('grade')

    return render(request, 'dashboard/schools/classes.html', {
        'classes': classes, 'school': school,
        'students_by_class': students_by_class,
        'outgoing': outgoing, 'incoming': incoming, 'completed': completed,
        'promotions': promotions, 'current_year': current_year, 'next_year': next_year,
        'young_students': young_students,
    })



@login_required
def manage_subject_textbooks(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    school = request.user.school
    classes_qs = Class.objects.filter(school=school)
    if request.method == 'POST':
        class_id = request.POST.get('class_id')
        subject = request.POST.get('subject', '').strip()
        textbook_id = request.POST.get('textbook_id')
        cls = Class.objects.get(id=class_id, school=school)
        SubjectTextbook.objects.get_or_create(school_class=cls, subject=subject, textbook_id=textbook_id)
        return redirect('dashboard:manage_subject_textbooks')
    assignments = SubjectTextbook.objects.filter(school_class__school=school).select_related('school_class', 'textbook')
    textbooks = Textbook.objects.all()
    return render(request, 'dashboard/catalog/subject_textbooks.html', {
        'assignments': assignments, 'classes': classes_qs, 'textbooks': textbooks,
    })


@login_required
def student_detail(request, student_id):
    if request.user.role not in ('superadmin', 'school_admin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    student = User.objects.get(id=student_id)
    if request.user.role == 'school_admin' and student.school != request.user.school:
        return render(request, 'dashboard/error.html', {'error': _('Пользователь из другой школы')})
    textbook_loans = TextbookLoan.objects.filter(student=student).select_related('textbook')
    book_loans = RegularBookLoan.objects.filter(user=student).select_related('book')
    achievements = student.achievements.select_related('achievement').all()
    streak = getattr(student, 'streak', None)
    level_info = getattr(student, 'level_info', None)
    return render(request, 'dashboard/users/student_detail.html', {
        'student': student, 'textbook_loans': textbook_loans,
        'book_loans': book_loans, 'achievements': achievements,
        'streak': streak, 'level_info': level_info,
    })


@login_required
def manage_young_students(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    classes = Class.objects.filter(school=request.user.school, number__lte=4, status=Class.Status.ACTIVE)
    students = User.objects.filter(school=request.user.school, role=User.Role.STUDENT, grade__in=classes, is_active_for_gamification=False)
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        class_id = request.POST.get('class_id')
        grade = Class.objects.get(id=class_id) if class_id else None
        if first_name and last_name and grade:
            User.objects.create(
                first_name=first_name, last_name=last_name,
                role=User.Role.STUDENT, school=request.user.school,
                grade=grade, is_active_for_gamification=False,
            )
        return redirect('dashboard:manage_classes')
    return redirect('dashboard:manage_classes')


@login_required
def multi_class_teacher_borrow(request):
    if request.user.role not in ('teacher', 'school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    user = request.user
    classes = Class.objects.filter(school=user.school, status=Class.Status.ACTIVE)
    textbooks = Textbook.objects.all()
    if user.role == 'teacher' and user.subject:
        show_all = request.GET.get('show_all') == '1'
        if not show_all:
            textbooks = textbooks.filter(subject__iexact=user.subject)
    if request.method == 'POST':
        class_ids = request.POST.getlist('class_ids')
        textbook_ids = request.POST.getlist('textbook_ids')
        teacher = user
        if request.user.role == 'school_admin':
            teacher_id = request.POST.get('teacher_id')
            teacher = User.objects.get(id=teacher_id)
        all_loans = []
        for class_id in class_ids:
            cls = Class.objects.get(id=class_id)
            for tb_id in textbook_ids:
                loans = issue_textbooks(user.school, teacher, [tb_id], request.user, 'teacher')
                all_loans.extend(loans)
        return redirect('dashboard:my_loans')
    teachers = User.objects.filter(school=user.school, role=User.Role.TEACHER) if user.role == 'school_admin' else []
    return render(request, 'dashboard/loans/multi_teacher_borrow.html', {
        'classes': classes, 'textbooks': textbooks, 'teachers': teachers,
    })


@login_required
def challenge_leaderboard(request):
    challenges = Challenge.objects.filter(status=Challenge.Status.PUBLISHED).order_by('-week_start')[:5]
    selected = None
    attempts = []
    user_rank = None
    user_attempt = None
    grade_numbers = []
    if request.GET.get('challenge_id'):
        selected = Challenge.objects.get(id=request.GET.get('challenge_id'))
        qs = ChallengeAttempt.objects.filter(challenge=selected, is_completed=True).select_related('user', 'user__grade').order_by('-score')
        if request.user.role == 'school_admin':
            qs = qs.filter(user__school=request.user.school)
        grade_param = request.GET.get('grade_number')
        if grade_param:
            qs = qs.filter(user__grade__number=int(grade_param))
        all_attempts = list(qs)
        attempts = all_attempts[:10]
        current = next((a for a in all_attempts if a.user_id == request.user.id), None)
        if current:
            user_rank = all_attempts.index(current) + 1
            if user_rank > 10:
                user_attempt = current
        grade_numbers = list(
            ChallengeAttempt.objects.filter(challenge=selected, is_completed=True)
            .values_list('user__grade__number', flat=True).distinct().order_by('user__grade__number')
        )
    return render(request, 'dashboard/challenges/leaderboard.html', {
        'challenges': challenges, 'selected': selected, 'attempts': attempts,
        'user_rank': user_rank, 'user_attempt': user_attempt, 'grade_numbers': grade_numbers,
    })


@login_required
def student_challenge(request):
    user = request.user
    if user.role != 'student':
        return redirect('dashboard:challenge_leaderboard')
    from apps.gamification.models import ChallengeAttempt, Challenge
    attempt = ChallengeAttempt.objects.filter(user=user, is_completed=False).order_by('-started_at').first()
    if attempt:
        return render(request, 'dashboard/challenges/take.html', {
            'questions': attempt.questions_data or attempt.challenge.questions,
            'attempt_id': str(attempt.id),
            'csrf_token': request.META.get('CSRF_COOKIE', ''),
        })
    active = Challenge.objects.filter(
        grade_number=user.grade.number if user.grade else None,
        status=Challenge.Status.PUBLISHED,
    ).order_by('-week_start').first()
    if active:
        return redirect('dashboard:student_challenge')
    return redirect('dashboard:challenge_leaderboard')


@login_required
def edit_profile(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        if first_name and last_name:
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()
    return redirect('dashboard:profile')


@login_required
def change_password(request):
    if request.method == 'POST':
        old = request.POST.get('old_password', '')
        new = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')
        if not request.user.check_password(old):
            return redirect('dashboard:profile')
        if len(new) < 6:
            return redirect('dashboard:profile')
        if new != confirm:
            return redirect('dashboard:profile')
        request.user.set_password(new)
        request.user.save()
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)
        return redirect('dashboard:profile')
    return redirect('dashboard:profile')


@login_required
def student_catalog(request):
    PAGE_SIZE = 50
    textbooks = Textbook.objects.all()
    books = RegularBook.objects.filter(school=request.user.school) if request.user.school else RegularBook.objects.none()
    q = request.GET.get('q', '').strip()
    if q:
        textbooks = textbooks.filter(Q(title__icontains=q) | Q(subject__icontains=q) | Q(author__icontains=q))
        books = books.filter(Q(title__icontains=q) | Q(author__icontains=q))
    page = request.GET.get('page', 1)
    paginator_textbooks = Paginator(textbooks, PAGE_SIZE)
    page_obj_textbooks = paginator_textbooks.get_page(page)
    paginator_books = Paginator(books, PAGE_SIZE)
    page_obj_books = paginator_books.get_page(page)
    return render(request, 'dashboard/catalog/student_catalog.html', {
        'page_obj_textbooks': page_obj_textbooks, 'page_obj_books': page_obj_books, 'q': q,
        'cart_ids': request.session.get('textbook_cart_ids', []),
    })


@login_required
def my_loans(request):
    textbook_loans = TextbookLoan.objects.filter(student=request.user).select_related('textbook')
    book_loans = RegularBookLoan.objects.filter(user=request.user).select_related('book')
    return render(request, 'dashboard/loans/my_loans.html', {
        'textbook_loans': textbook_loans,
        'book_loans': book_loans,
    })


@login_required
def news_list(request):
    news = NewsService.visible_to(request.user)
    return render(request, 'dashboard/news/list.html', {'news': news})


@login_required
def news_create(request):
    if request.user.role not in ('superadmin', 'school_admin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        if title and content:
            News.objects.create(
                title=title, content=content,
                author=request.user,
                author_level=News.AuthorLevel.SUPERADMIN if request.user.role == 'superadmin' else News.AuthorLevel.SCHOOL_ADMIN,
                school=None if request.user.role == 'superadmin' else request.user.school,
                is_published=request.POST.get('is_published') == '1',
                published_at=timezone.now() if request.POST.get('is_published') == '1' else None,
            )
        return redirect('dashboard:news_list')
    return render(request, 'dashboard/news/create.html')


CART_SESSION_KEY = 'textbook_cart_ids'

@login_required
def add_to_cart(request):
    textbook_id = request.GET.get('id')
    if textbook_id:
        cart = request.session.get(CART_SESSION_KEY, [])
        if textbook_id not in cart:
            cart.append(textbook_id)
            request.session[CART_SESSION_KEY] = cart
    return redirect(request.META.get('HTTP_REFERER', 'dashboard:textbook_cart'))


@login_required
def remove_from_cart(request):
    textbook_id = request.GET.get('id')
    cart = request.session.get(CART_SESSION_KEY, [])
    if textbook_id in cart:
        cart.remove(textbook_id)
        request.session[CART_SESSION_KEY] = cart
    return redirect(request.META.get('HTTP_REFERER', 'dashboard:textbook_cart'))


@login_required
def cart_counter_fragment(request):
    cart = request.session.get(CART_SESSION_KEY, [])
    count = len(cart)
    return HttpResponse(f'<span class="cart-count" id="cart-counter">{count}</span>')


@login_required
def student_textbook_cart(request):
    if request.user.role not in ('student', 'teacher', 'school_admin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    user = request.user
    cart_ids = request.session.get(CART_SESSION_KEY, [])
    textbooks = Textbook.objects.filter(id__in=cart_ids) if cart_ids else Textbook.objects.none()
    if request.method == 'POST':
        textbook_ids = request.session.pop(CART_SESSION_KEY, [])
        if textbook_ids:
            payload = {
                'school_id': str(user.school_id),
                'user_id': str(user.id),
                'item_ids': [str(i) for i in textbook_ids],
                'item_type': 'textbook',
            }
            request.session['qr_payload'] = payload
            token = create_issue_token(user.school_id, str(user.id), textbook_ids, 'textbook')
            request.session['current_token'] = token
            return redirect('dashboard:qr_issue')
    return render(request, 'dashboard/catalog/textbook_cart.html', {
        'textbooks': textbooks,
    })


@login_required
def qr_issue(request):
    token = request.session.get('current_token')
    payload = request.session.get('qr_payload')
    if not token or not payload:
        return redirect('dashboard:textbook_cart')
    exp = None
    try:
        dot = token.rfind('.')
        exp = json.loads(token[:dot]).get('exp', 0)
    except Exception:
        pass
    return render(request, 'dashboard/qr/qr_issue.html', {
        'token': token,
        'exp': exp,
        'count': len(payload.get('item_ids', [])),
    })


@login_required
def qr_issue_refresh(request):
    payload = request.session.get('qr_payload')
    if not payload:
        return HttpResponse('<div class="alert alert-error">Сессия истекла</div>')
    from apps.loans.services import generate_qr_token
    new_token = generate_qr_token(payload)
    request.session['current_token'] = new_token
    exp = None
    try:
        dot = new_token.rfind('.')
        exp = json.loads(new_token[:dot]).get('exp', 0)
    except Exception:
        pass
    return render(request, 'dashboard/qr/_qr_fragment.html', {
        'token': new_token,
        'exp': exp,
    })


@login_required
def notification_badge(request):
    count = request.user.notifications.filter(is_read=False).count()
    return HttpResponse(f'<span id="notif-count">{count}</span>')


@login_required
def notification_list(request):
    notifs = request.user.notifications.all()[:5]
    return render(request, 'dashboard/notifications/_dropdown.html', {'notifications': notifs})


@login_required
def mark_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return HttpResponse('')


@login_required
def qr_return_loans(request):
    if request.method != 'POST':
        return redirect('dashboard:my_loans')
    user = request.user
    loan_ids = request.POST.getlist('loan_ids')
    item_type = request.POST.get('item_type', 'book')
    if not loan_ids:
        return redirect('dashboard:my_loans')
    remaining = 0
    if item_type == 'textbook':
        total_active = TextbookLoan.objects.filter(student=user, status=TextbookLoan.Status.ACTIVE).count()
        remaining = total_active - len(loan_ids)
    else:
        total_active = RegularBookLoan.objects.filter(user=user, status=RegularBookLoan.Status.ACTIVE).count()
        remaining = total_active - len(loan_ids)
    token = create_return_token(user.school_id, str(user.id), loan_ids, item_type)
    payload = {
        'school_id': str(user.school_id),
        'user_id': str(user.id),
        'loan_ids': [str(i) for i in loan_ids],
        'item_type': item_type,
        'action': 'return',
    }
    request.session['qr_payload'] = payload
    request.session['current_token'] = token
    exp = None
    try:
        dot = token.rfind('.')
        exp = json.loads(token[:dot]).get('exp', 0)
    except Exception:
        pass
    return render(request, 'dashboard/qr/qr_return.html', {
        'token': token,
        'exp': exp,
        'count': len(loan_ids),
        'remaining': remaining,
    })


@login_required
def homeroom_dashboard(request):
    if request.user.role != 'teacher':
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from django.db.models import Count, Q
    classes = list(request.user.homeroom_classes.filter(status=Class.Status.ACTIVE))
    students = User.objects.filter(grade__in=classes, role=User.Role.STUDENT).annotate(
        textbook_active=Count('textbook_loans', filter=Q(textbook_loans__status__in=['active', 'overdue'])),
        book_active=Count('book_loans', filter=Q(book_loans__status__in=['active', 'overdue'])),
    ).select_related('level_info', 'streak')
    return render(request, 'dashboard/teacher/homeroom.html', {'classes': classes, 'students': students})


@login_required
def import_csv_view(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    if request.method == 'POST':
        import csv, io
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            return render(request, 'dashboard/users/import_csv.html', {'error': 'Файл не загружен'})
        decoded = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        results = []
        errors = []
        for lineno, row in enumerate(reader, start=2):
            first_name = row.get('ФИО', '').strip().split()[0] if row.get('ФИО') else ''
            last_name = ' '.join(row.get('ФИО', '').strip().split()[1:]) if row.get('ФИО') else ''
            grade_num = row.get('Класс', '').strip()
            grade = None
            if grade_num:
                try:
                    grade, _ = Class.objects.get_or_create(
                        school=request.user.school, number=int(grade_num),
                        defaults={'parallel': '', 'language': 'ru', 'academic_year': str(timezone.now().year)},
                    )
                except (ValueError, TypeError):
                    errors.append(f'Строка {lineno}: неверный номер класса "{grade_num}"')
                    continue
            if not first_name or not last_name:
                errors.append(f'Строка {lineno}: пустое ФИО')
                continue
            try:
                user, password = create_user(
                    role=User.Role.STUDENT,
                    first_name=first_name, last_name=last_name,
                    school=request.user.school, grade=grade,
                )
                results.append({'user': user, 'password': password})
            except Exception as e:
                errors.append(f'Строка {lineno}: {e}')
        if errors and not results:
            return render(request, 'dashboard/users/import_csv.html', {'error': '; '.join(errors)})
        rows = [[r['user'].last_name + ' ' + r['user'].first_name, str(r['user'].grade), r['user'].login, r['password']] for r in results]
        return export_to_excel(
            headers=['ФИО', 'Класс', 'Логин', 'Пароль'],
            rows=rows,
            filename='import_results.xlsx',
        )
    return render(request, 'dashboard/users/import_csv.html')


@login_required
def school_settings(request):
    return redirect('dashboard:manage_classes')


@login_required
@require_POST
def promote_classes_view(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from apps.schools.services import auto_promote_classes
    school = request.user.school
    current_year = request.POST.get('current_year', '').strip()
    next_year = request.POST.get('next_year', '').strip()
    if not current_year or not next_year:
        return redirect('dashboard:manage_classes')
    try:
        promoted = auto_promote_classes(school, current_year, next_year, initiated_by=request.user)
        from django.contrib import messages
        messages.success(request, _('Классы успешно переведены на следующий год'))
        return redirect('dashboard:manage_classes')
    except ValueError as e:
        from django.contrib import messages
        messages.error(request, str(e))
        return redirect('dashboard:manage_classes')


@login_required
def transfers_list(request):
    return redirect('dashboard:manage_classes')


@login_required
@require_POST
def transfer_depart(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from django.contrib import messages
    from apps.schools.transfer_service import initiate_departure, complete_departure
    user_id = request.POST.get('user_id')
    action = request.POST.get('action', 'initiate')
    if action == 'initiate':
        target = User.objects.get(id=user_id)
        if target.school != request.user.school:
            messages.error(request, _('Пользователь из другой школы'))
            return redirect('dashboard:manage_classes')
        transfer, err = initiate_departure(target, request.user)
        if err:
            messages.error(request, err)
            return redirect('dashboard:manage_classes')
        messages.success(request, _('Уход оформлен'))
    elif action == 'complete':
        transfer, err = complete_departure(user_id, request.user)
        if err:
            messages.error(request, err)
            return redirect('dashboard:manage_classes')
        messages.success(request, _('Уход подтверждён'))
    return redirect('dashboard:manage_classes')


@login_required
@require_POST
def transfer_accept(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from django.contrib import messages
    from apps.schools.transfer_service import accept_transfer
    user_login = request.POST.get('user_login', '').strip()
    if not user_login:
        return redirect('dashboard:manage_classes')
    target = User.objects.filter(login=user_login).first()
    if not target:
        messages.error(request, _('Пользователь не найден'))
        return redirect('dashboard:manage_classes')
    transfer, err = accept_transfer(target.id, request.user.school, request.user)
    if err:
        messages.error(request, err)
        return redirect('dashboard:manage_classes')
    messages.success(request, _('Ученик принят в школу'))
    return redirect('dashboard:manage_classes')


@login_required
def textbook_detail(request, textbook_id):
    from django.shortcuts import get_object_or_404
    textbook = get_object_or_404(Textbook, id=textbook_id)
    return render(request, 'dashboard/catalog/textbook_detail.html', {'textbook': textbook})


@login_required
def book_detail(request, book_id):
    from django.shortcuts import get_object_or_404
    book = get_object_or_404(RegularBook, id=book_id)
    if request.user.role != 'superadmin' and book.school != request.user.school:
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    return render(request, 'dashboard/catalog/book_detail.html', {'book': book})


@login_required
def manage_admins(request):
    if request.user.role != 'superadmin':
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from django.contrib import messages
    from apps.accounts.services import generate_password

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_school_id = request.POST.get('new_school_id')
        action = request.POST.get('action')

        if action == 'transfer' and user_id and new_school_id:
            admin = User.objects.filter(id=user_id, role=User.Role.SCHOOL_ADMIN).first()
            new_school = School.objects.filter(id=new_school_id).first()
            if admin and new_school:
                old_school = admin.school
                admin.school = new_school
                admin.save()
                ActionLog.objects.filter(user=admin, school=old_school).update(school=new_school)
                TextbookLoan.objects.filter(issued_by=admin, school=old_school).update(school=new_school)
                RegularBookLoan.objects.filter(issued_by=admin, school=old_school).update(school=new_school)
                News.objects.filter(author=admin, school=old_school).update(school=new_school)
                ActionLog.objects.create(
                    school=new_school, user=request.user,
                    action=ActionLog.ActionType.TRANSFER,
                    details={'admin_id': str(admin.id), 'from_school': str(old_school.id), 'to_school': str(new_school.id)},
                )
                messages.success(request, _('Администратор переведён в новую школу'))
            else:
                messages.error(request, _('Администратор или школа не найдены'))
        elif action == 'reset_password' and user_id:
            admin = User.objects.filter(id=user_id, role=User.Role.SCHOOL_ADMIN).first()
            if admin:
                new_password = generate_password()
                admin.set_password(new_password)
                admin.save()
                messages.success(request, f'Новый пароль для {admin.login}: {new_password}')
        elif action == 'create':
            from apps.accounts.services import generate_login, generate_password
            school_id = request.POST.get('school_id')
            school = School.objects.filter(id=school_id).first()
            if school:
                admin_login = generate_login('admin', school.name[:20].replace(' ', '_').lower(), school.id)
                admin_pwd = generate_password()
                admin = User.objects.create_user(
                    login=admin_login, password=admin_pwd,
                    school=school, role=User.Role.SCHOOL_ADMIN,
                )
                messages.success(request, _('Администратор создан: %(login)s / %(password)s') % {'login': admin_login, 'password': admin_pwd})
        return redirect('dashboard:manage_admins')

    schools = School.objects.select_related('district').annotate(
        admin_count=Count('user', filter=Q(user__role=User.Role.SCHOOL_ADMIN)),
        student_count=Count('user', filter=Q(user__role=User.Role.STUDENT)),
    ).order_by('name')
    admins = User.objects.filter(role=User.Role.SCHOOL_ADMIN).select_related('school__district')
    return render(request, 'dashboard/schools/manage_admins.html', {
        'schools': schools,
        'admins': admins,
    })
