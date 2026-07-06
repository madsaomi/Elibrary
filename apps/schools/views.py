from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.schools.models import District, School, Class, TransferLog
from apps.schools.serializers import (
    DistrictSerializer, SchoolSerializer, ClassSerializer, TransferLogSerializer,
    InitiateTransferSerializer, AcceptTransferSerializer,
)
from apps.schools.transfer_service import initiate_departure, complete_departure, accept_transfer, cancel_transfer
from api.v1.permissions import IsSuperAdmin, IsSchoolAdminOrSuperAdmin, IsSchoolAdmin, IsOwnerOrSchoolAdmin
from apps.accounts.models import User


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'superadmin'


class IsSchoolAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('superadmin', 'school_admin')


class DistrictViewSet(viewsets.ModelViewSet):
    queryset = District.objects.all()
    serializer_class = DistrictSerializer
    permission_classes = [IsSuperAdmin]


class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [IsSuperAdmin]


class ClassViewSet(viewsets.ModelViewSet):
    queryset = Class.objects.all()
    serializer_class = ClassSerializer
    permission_classes = [IsSchoolAdmin]

    def get_queryset(self):
        qs = Class.objects.all()
        if self.request.user.role == 'school_admin':
            qs = qs.filter(school=self.request.user.school)
        return qs


class TransferViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TransferLog.objects.all()
    serializer_class = TransferLogSerializer
    permission_classes = [IsSchoolAdmin]

    def get_queryset(self):
        qs = TransferLog.objects.all()
        user = self.request.user
        if user.role == 'school_admin':
            qs = qs.filter(from_school=user.school) | qs.filter(to_school=user.school)
        return qs

    @action(detail=False, methods=['post'])
    def initiate(self, request):
        serializer = InitiateTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.get(id=serializer.validated_data['user_id'])
        if user.school != request.user.school:
            return Response({'error': 'Пользователь из другой школы'}, status=status.HTTP_400_BAD_REQUEST)
        transfer, error = initiate_departure(user, request.user)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TransferLogSerializer(transfer).data)

    @action(detail=False, methods=['post'])
    def complete_departure(self, request):
        serializer = InitiateTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer, error = complete_departure(serializer.validated_data['user_id'], request.user)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TransferLogSerializer(transfer).data)

    @action(detail=False, methods=['post'])
    def accept(self, request):
        serializer = AcceptTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        to_school = School.objects.get(id=serializer.validated_data['to_school_id'])
        transfer, error = accept_transfer(serializer.validated_data['user_id'], to_school, request.user)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TransferLogSerializer(transfer).data)

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        serializer = InitiateTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer, error = cancel_transfer(serializer.validated_data['user_id'])
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TransferLogSerializer(transfer).data)
