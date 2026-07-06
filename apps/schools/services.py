import secrets
import string

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.services import generate_login, generate_password
from apps.schools.models import District, School, Class


@transaction.atomic
def create_district(name):
    return District.objects.create(name=name)


@transaction.atomic
def create_school(name, district_id):
    district = District.objects.get(id=district_id)
    school = School.objects.create(name=name, district=district)

    admin_password = generate_password()
    admin_login = generate_login('admin', name.replace(' ', '_').lower(), school.id)
    admin = User.objects.create(
        login=admin_login,
        first_name='Admin',
        last_name=name,
        role=User.Role.SCHOOL_ADMIN,
        school=school,
    )
    admin.set_password(admin_password)
    admin.save()

    return school, admin, admin_password


@transaction.atomic
def create_class(school, number, parallel, language, academic_year):
    return Class.objects.create(
        school=school,
        number=number,
        parallel=parallel,
        language=language,
        academic_year=academic_year,
    )


@transaction.atomic
def auto_promote_classes(school, current_academic_year, next_academic_year, initiated_by=None):
    from apps.schools.models import PromotionLog
    if PromotionLog.objects.filter(school=school, academic_year=next_academic_year).exists():
        raise ValueError('Автоперевод для этого учебного года уже был выполнен.')

    from django.db.models import Q
    classes = Class.objects.filter(school=school, academic_year=current_academic_year, status=Class.Status.ACTIVE)

    promoted = []
    for cls in classes:
        if cls.number < 11:
            new_cls, created = Class.objects.get_or_create(
                school=school,
                number=cls.number + 1,
                parallel=cls.parallel,
                language=cls.language,
                academic_year=next_academic_year,
                defaults={'status': Class.Status.ACTIVE},
            )
            promoted.append({'from': cls, 'to': new_cls, 'created': created})
            cls.status = Class.Status.GRADUATED if cls.number == 11 else Class.Status.ACTIVE
            cls.save()
        else:
            cls.status = Class.Status.GRADUATED
            cls.save()
            promoted.append({'from': cls, 'to': None, 'created': False})

    next_classes = {
        (c.number, c.parallel, c.language): c
        for c in Class.objects.filter(school=school, academic_year=next_academic_year)
    }
    users = User.objects.filter(school=school, role=User.Role.STUDENT, grade__academic_year=current_academic_year)
    for user in users:
        if user.grade and user.grade.number < 11:
            new_number = user.grade.number + 1
            key = (new_number, user.grade.parallel, user.grade.language)
            new_cls = next_classes.get(key) or Class.objects.get_or_create(
                school=school, number=new_number, parallel=user.grade.parallel,
                language=user.grade.language, academic_year=next_academic_year,
                defaults={'status': Class.Status.ACTIVE},
            )[0]
            next_classes[key] = new_cls
            user.grade = new_cls
            user.save()
        elif user.grade and user.grade.number == 11:
            user.grade = None
            user.is_active = False
            user.save()

    PromotionLog.objects.create(
        school=school,
        academic_year=next_academic_year,
        initiated_by=initiated_by
    )

    return promoted
