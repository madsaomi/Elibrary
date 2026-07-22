from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.catalog.models import Textbook, RegularBook, SubjectTextbook
from apps.loans.models import TextbookLoan, RegularBookLoan
from apps.loans.services import (
    issue_textbooks, return_textbooks, issue_books,
    get_student_textbook_set, issue_textbooks_to_class,
)
from apps.schools.models import Class
from apps.stats.models import ActionLog
from apps.core.services import export_to_excel


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
        from django.http import HttpResponse
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
def issue_textbooks_view(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    student_id = request.GET.get('student_id')
    if student_id:
        return redirect('dashboard:issue_textbooks_set', student_id=student_id)
    students = User.objects.filter(school=request.user.school, role=User.Role.STUDENT).select_related('grade')
    if request.method == 'POST':
        from django.contrib import messages
        student_id = request.POST.get('student_id')
        textbook_ids = request.POST.getlist('textbook_ids')
        student = User.objects.get(id=student_id)
        loans, skipped = issue_textbooks(request.user.school, student, textbook_ids, request.user, 'student')
        if skipped:
            messages.warning(request, _('Пропущено: %(count)d учебников (нет остатка или уже выдано)') % {'count': len(skipped)})
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
def issue_textbooks_set_view(request, student_id):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from django.shortcuts import get_object_or_404
    from django.contrib import messages
    student = get_object_or_404(User, id=student_id)
    textbook_set = get_student_textbook_set(student)
    if request.method == 'POST':
        textbook_ids = request.POST.getlist('textbook_ids')
        loans, skipped = issue_textbooks(request.user.school, student, textbook_ids, request.user, 'student')
        if skipped:
            messages.warning(request, _('Пропущено: %(count)d учебников') % {'count': len(skipped)})
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
    from django.contrib import messages
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
        loans, skipped = issue_textbooks(user.school, teacher, textbook_ids, request.user, 'teacher')
        if skipped:
            messages.warning(request, _('Пропущено: %(count)d учебников') % {'count': len(skipped)})
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
def teacher_books_view(request):
    if request.user.role not in ('teacher', 'school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from django.contrib import messages
    user = request.user
    books = RegularBook.objects.filter(school=user.school)
    if request.method == 'POST':
        book_ids = request.POST.getlist('book_ids')
        borrower = user
        if request.user.role == 'school_admin':
            teacher_id = request.POST.get('teacher_id')
            borrower = User.objects.get(id=teacher_id)
        loans, skipped = issue_books(user.school, borrower, book_ids, request.user)
        if skipped:
            messages.warning(request, _('Пропущено: %(count)d книг (нет остатка)') % {'count': len(skipped)})
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
def my_loans(request):
    textbook_loans = TextbookLoan.objects.filter(student=request.user).select_related('textbook')
    book_loans = RegularBookLoan.objects.filter(user=request.user).select_related('book')
    return render(request, 'dashboard/loans/my_loans.html', {
        'textbook_loans': textbook_loans,
        'book_loans': book_loans,
    })


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
        all_skipped = []
        for class_id in class_ids:
            cls = Class.objects.get(id=class_id)
            for tb_id in textbook_ids:
                loans, skipped = issue_textbooks(user.school, teacher, [tb_id], request.user, 'teacher')
                all_loans.extend(loans)
                all_skipped.extend(skipped)
        return redirect('dashboard:my_loans')
    teachers = User.objects.filter(school=user.school, role=User.Role.TEACHER) if user.role == 'school_admin' else []
    return render(request, 'dashboard/loans/multi_teacher_borrow.html', {
        'classes': classes, 'textbooks': textbooks, 'teachers': teachers,
    })
