from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.db.models import Q, Count
from django.contrib.sessions.models import Session
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.accounts.services import create_user, reset_password, activate_grade_access
from apps.loans.models import TextbookLoan, RegularBookLoan
from apps.schools.models import Class
from apps.core.services import export_to_excel


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
        Session.objects.all().delete()
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
            from apps.accounts.services import to_latin
            User.objects.create(
                first_name=to_latin(first_name), last_name=to_latin(last_name),
                role=User.Role.STUDENT, school=request.user.school,
                grade=grade, is_active_for_gamification=False,
            )
        return redirect('dashboard:manage_classes')
    return redirect('dashboard:manage_classes')


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
