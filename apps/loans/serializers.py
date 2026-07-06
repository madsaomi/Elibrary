from rest_framework import serializers

from apps.loans.models import TextbookLoan, RegularBookLoan


class TextbookLoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextbookLoan
        fields = '__all__'
        read_only_fields = ['school', 'student', 'textbook', 'issued_by', 'issued_at', 'returned_at']


class RegularBookLoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegularBookLoan
        fields = '__all__'
        read_only_fields = ['school', 'user', 'book', 'issued_by', 'issued_at', 'returned_at', 'qr_token']
