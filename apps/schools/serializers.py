from rest_framework import serializers

from apps.schools.models import District, School, Class, TransferLog


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = '__all__'


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = '__all__'


class ClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = Class
        fields = '__all__'


class TransferLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferLog
        fields = '__all__'
        read_only_fields = ('xp_before', 'xp_after', 'completed_at')


class InitiateTransferSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()


class AcceptTransferSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    to_school_id = serializers.UUIDField()
