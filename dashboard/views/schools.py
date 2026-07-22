from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.catalog.models import Textbook, SubjectTextbook
from apps.loans.models import TextbookLoan, RegularBookLoan
from apps.notifications.models import News
from apps.schools.models import School, District, Class, TransferLog
from apps.stats.models import ActionLog


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

    students_by_class = {}
    if school:
        students_qs = User.objects.filter(school=school, role='student').select_related('grade').only('id', 'first_name', 'last_name', 'login', 'grade')

    for s in students_qs:
        if s.grade_id:
            students_by_class.setdefault(str(s.grade_id), []).append(s)

    from apps.schools.models import TransferLog, PromotionLog
    outgoing = incoming = completed = []
    young_students = []
    current_year = next_year = ''
    promotions = []

    if school:
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
        promotions = PromotionLog.objects.filter(school=school).order_by('-created_at')[:10]
        current_year = str(timezone.now().year - 1) + '-' + str(timezone.now().year)
        next_year = str(timezone.now().year) + '-' + str(timezone.now().year + 1)
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
            from apps.accounts.services import create_user
            user, password = create_user(
                role='student', first_name=first_name, last_name=last_name,
                school=school, grade=cls,
            )
            messages.success(request, f'{user.get_full_name()} создан(а) и добавлен(а) в {cls.number}{cls.parallel}. Пароль: {password}')
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
def manage_admins(request):
    if request.user.role != 'superadmin':
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from django.contrib import messages
    from apps.accounts.services import reset_password

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
                new_password = reset_password(admin)
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


@login_required
def school_settings(request):
    return redirect('dashboard:manage_classes')


@login_required
def promote_classes_view(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from django.contrib import messages
    from apps.schools.services import auto_promote_classes
    school = request.user.school
    current_year = request.POST.get('current_year', '').strip()
    next_year = request.POST.get('next_year', '').strip()
    if not current_year or not next_year:
        return redirect('dashboard:manage_classes')
    try:
        promoted = auto_promote_classes(school, current_year, next_year, initiated_by=request.user)
        messages.success(request, _('Классы успешно переведены на следующий год'))
        return redirect('dashboard:manage_classes')
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('dashboard:manage_classes')


@login_required
def transfers_list(request):
    return redirect('dashboard:manage_classes')


@login_required
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
