import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.utils.translation import gettext as _

from apps.catalog.models import RegularBook
from apps.loans.models import TextbookLoan, RegularBookLoan
from apps.loans.services import create_issue_token, create_return_token, process_qr_return


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
