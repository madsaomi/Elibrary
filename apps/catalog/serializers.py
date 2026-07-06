from rest_framework import serializers

from apps.catalog.models import Category, Textbook, TextbookStock, RegularBook


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class TextbookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Textbook
        fields = '__all__'


class TextbookStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextbookStock
        fields = '__all__'


class RegularBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegularBook
        fields = '__all__'
