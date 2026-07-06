from django.contrib import admin

from apps.schools.models import District, School, Class


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'district')
    list_filter = ('district',)
    search_fields = ('name',)


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('number', 'parallel', 'language', 'academic_year', 'school', 'status')
    list_filter = ('school', 'status', 'language')
    search_fields = ('school__name',)
