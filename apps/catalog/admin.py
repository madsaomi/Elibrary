from django.contrib import admin

from apps.catalog.models import Category, Textbook, TextbookStock, RegularBook


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Textbook)
class TextbookAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'grade_number', 'language', 'academic_year')
    list_filter = ('subject', 'grade_number', 'language')
    search_fields = ('title',)


@admin.register(TextbookStock)
class TextbookStockAdmin(admin.ModelAdmin):
    list_display = ('textbook', 'school', 'total_copies', 'available_copies')
    list_filter = ('school',)


@admin.register(RegularBook)
class RegularBookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'school', 'category', 'total_copies', 'available_copies')
    list_filter = ('school', 'category')
    search_fields = ('title', 'author')
