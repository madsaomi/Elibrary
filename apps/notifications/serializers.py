from rest_framework import serializers

from apps.notifications.models import News


class NewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = News
        fields = '__all__'
        read_only_fields = ['author', 'author_level', 'school']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['author'] = user
        validated_data['author_level'] = user.role
        if user.role == 'school_admin':
            validated_data['school'] = user.school
        elif user.role == 'superadmin':
            validated_data['school'] = None
        return super().create(validated_data)
