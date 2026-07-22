from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Q, Count, Avg
from django.utils.translation import gettext as _
from datetime import date

from apps.accounts.models import User
from apps.loans.models import TextbookLoan
from apps.schools.models import School, District
from apps.core.services import generate_return_list_excel
from dashboard.services import get_school_stats


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
def return_list_export(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    school = request.user.school
    from apps.catalog.models import SubjectTextbook
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
