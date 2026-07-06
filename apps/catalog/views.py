from rest_framework import viewsets, permissions

from apps.catalog.models import Category, Textbook, TextbookStock, RegularBook
from apps.catalog.serializers import CategorySerializer, TextbookSerializer, TextbookStockSerializer, RegularBookSerializer
from api.v1.permissions import IsSuperAdmin, IsSchoolAdminOrSuperAdmin


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsSuperAdmin]


class TextbookViewSet(viewsets.ModelViewSet):
    queryset = Textbook.objects.all()
    serializer_class = TextbookSerializer
    permission_classes = [permissions.IsAuthenticated]


class TextbookStockViewSet(viewsets.ModelViewSet):
    queryset = TextbookStock.objects.all()
    serializer_class = TextbookStockSerializer
    permission_classes = [IsSchoolAdminOrSuperAdmin]

    def get_queryset(self):
        qs = TextbookStock.objects.all()
        if self.request.user.role == 'school_admin':
            qs = qs.filter(school=self.request.user.school)
        return qs


class RegularBookViewSet(viewsets.ModelViewSet):
    queryset = RegularBook.objects.all()
    serializer_class = RegularBookSerializer
    permission_classes = [IsSchoolAdminOrSuperAdmin]

    def get_queryset(self):
        qs = RegularBook.objects.all()
        if self.request.user.role == 'school_admin':
            qs = qs.filter(school=self.request.user.school)
        return qs
