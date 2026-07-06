from django.contrib import admin

from apps.loans.models import TextbookLoan, RegularBookLoan


@admin.register(TextbookLoan)
class TextbookLoanAdmin(admin.ModelAdmin):
    list_display = ('textbook', 'student', 'status', 'issued_at', 'due_date', 'school')
    list_filter = ('status', 'school')
    search_fields = ('student__first_name', 'student__last_name', 'textbook__title')


@admin.register(RegularBookLoan)
class RegularBookLoanAdmin(admin.ModelAdmin):
    list_display = ('book', 'user', 'status', 'issued_at', 'school')
    list_filter = ('status', 'school')
    search_fields = ('user__first_name', 'user__last_name', 'book__title')
