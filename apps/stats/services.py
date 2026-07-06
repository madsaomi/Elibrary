from apps.stats.models import ActionLog


def log_action(user, action, school=None, details=None):
    if school is None:
        school = user.school if user else None
    ActionLog.objects.create(
        user=user,
        school=school,
        action=action,
        details=details or {},
    )
