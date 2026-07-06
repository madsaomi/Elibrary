from django.conf import settings


def theme(request):
    return {'theme': request.COOKIES.get('theme', 'light')}


def current_language(request):
    lang = request.COOKIES.get('django_language', '')
    if not lang:
        lang = getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE)
    return {'current_language': lang}
