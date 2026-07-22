from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils.translation import gettext as _

from apps.catalog.models import Textbook, RegularBook, Category, SubjectTextbook, TextbookStock
from apps.loans.services import create_issue_token


CART_SESSION_KEY = 'textbook_cart_ids'


@login_required
def textbooks_list(request):
    PAGE_SIZE = 50
    textbooks = Textbook.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        textbooks = textbooks.filter(Q(title__icontains=q) | Q(subject__icontains=q) | Q(academic_year__icontains=q))
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
def textbook_detail(request, textbook_id):
    from django.shortcuts import get_object_or_404
    textbook = get_object_or_404(Textbook, id=textbook_id)
    return render(request, 'dashboard/catalog/textbook_detail.html', {'textbook': textbook})


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
def book_detail(request, book_id):
    from django.shortcuts import get_object_or_404
    book = get_object_or_404(RegularBook, id=book_id)
    if request.user.role != 'superadmin' and book.school != request.user.school:
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    return render(request, 'dashboard/catalog/book_detail.html', {'book': book})


@login_required
def student_catalog(request):
    PAGE_SIZE = 50
    textbooks = Textbook.objects.all()
    books = RegularBook.objects.filter(school=request.user.school) if request.user.school else RegularBook.objects.none()
    q = request.GET.get('q', '').strip()
    if q:
        textbooks = textbooks.filter(Q(title__icontains=q) | Q(subject__icontains=q) | Q(academic_year__icontains=q))
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
            token = create_issue_token(user.school_id, str(user.id), textbook_ids, 'textbook')
            request.session['current_token'] = token
            return redirect('dashboard:qr_issue')
    return render(request, 'dashboard/catalog/textbook_cart.html', {
        'textbooks': textbooks,
    })


@login_required
def manage_subject_textbooks(request):
    if request.user.role not in ('school_admin', 'superadmin'):
        return render(request, 'dashboard/error.html', {'error': _('Доступ запрещён')})
    from apps.schools.models import Class
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
