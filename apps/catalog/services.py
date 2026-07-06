from django.db import transaction

from apps.catalog.models import Textbook, TextbookStock, RegularBook, Category


@transaction.atomic
def create_textbook(title, subject, grade_number, language, academic_year, cover=None):
    textbook, created = Textbook.objects.get_or_create(
        title=title, subject=subject, grade_number=grade_number,
        language=language, academic_year=academic_year,
        defaults={'cover': cover},
    )
    return textbook, created


@transaction.atomic
def add_textbook_stock(school, textbook, total_copies):
    stock, created = TextbookStock.objects.get_or_create(
        school=school, textbook=textbook,
        defaults={'total_copies': total_copies, 'available_copies': total_copies},
    )
    if not created:
        stock.total_copies += total_copies
        stock.available_copies += total_copies
        stock.save()
    return stock


@transaction.atomic
def create_regular_book(school, title, author='', category=None, total_copies=1, cover=None):
    book, created = RegularBook.objects.get_or_create(
        school=school, title=title, author=author,
        defaults={
            'category': category,
            'total_copies': total_copies,
            'available_copies': total_copies,
            'cover': cover,
        },
    )
    if not created:
        book.total_copies += total_copies
        book.available_copies += total_copies
        if cover:
            book.cover = cover
        if category:
            book.category = category
        book.save()
    return book, created
