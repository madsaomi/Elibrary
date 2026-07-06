from rest_framework import serializers

from apps.loans.models import TextbookLoan, RegularBookLoan


class TextbookLoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextbookLoan
        fields = '__all__'


class RegularBookLoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegularBookLoan
        fields = '__all__'
