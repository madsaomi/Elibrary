from rest_framework import permissions


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'superadmin'


class IsSchoolAdminOrSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('superadmin', 'school_admin')


class IsSchoolAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'school_admin'


class IsTeacherOrAbove(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('superadmin', 'school_admin', 'teacher')


class ReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class IsOwnerOrSchoolAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'superadmin':
            return True
        if request.user.role == 'school_admin':
            school = getattr(obj, 'school', None)
            return school == request.user.school
        user_field = getattr(obj, 'user', None) or getattr(obj, 'student', None)
        return user_field == request.user


class IsLoanReaderOrAdmin(permissions.BasePermission):
    """Students/teachers can read (list/retrieve), only admins can write."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.role in ('superadmin', 'school_admin')
