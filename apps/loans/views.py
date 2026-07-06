from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.loans.models import TextbookLoan, RegularBookLoan
from apps.loans.serializers import TextbookLoanSerializer, RegularBookLoanSerializer
from apps.loans.services import issue_textbooks, return_textbooks, issue_books, return_books as return_books_service, create_issue_token, process_qr_issue, process_qr_return
from api.v1.permissions import IsSchoolAdminOrSuperAdmin


class TextbookLoanViewSet(viewsets.ModelViewSet):
    queryset = TextbookLoan.objects.all()
    serializer_class = TextbookLoanSerializer
    permission_classes = [IsSchoolAdminOrSuperAdmin]

    def get_queryset(self):
        qs = TextbookLoan.objects.all()
        user = self.request.user
        if user.role == 'student':
            qs = qs.filter(student=user)
        elif user.role == 'school_admin':
            qs = qs.filter(school=user.school)
        return qs

    @action(detail=False, methods=['post'])
    def issue(self, request):
        student_id = request.data.get('student_id')
        textbook_ids = request.data.get('textbook_ids', [])
        try:
            student = User.objects.get(id=student_id, school=request.user.school)
        except User.DoesNotExist:
            return Response({'error': 'Ученик не найден в вашей школе'}, status=status.HTTP_404_NOT_FOUND)
        loans = issue_textbooks(request.user.school, student, textbook_ids, request.user)
        return Response(TextbookLoanSerializer(loans, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def return_books(self, request):
        loan_ids = request.data.get('loan_ids', [])
        forced = request.data.get('forced', False)
        loans = return_textbooks(loan_ids, request.user, forced)
        return Response(TextbookLoanSerializer(loans, many=True).data)


class RegularBookLoanViewSet(viewsets.ModelViewSet):
    queryset = RegularBookLoan.objects.all()
    serializer_class = RegularBookLoanSerializer
    permission_classes = [IsSchoolAdminOrSuperAdmin]

    def get_queryset(self):
        qs = RegularBookLoan.objects.all()
        user = self.request.user
        if user.role == 'student':
            qs = qs.filter(user=user)
        elif user.role in ('teacher', 'school_admin'):
            qs = qs.filter(school=user.school)
        return qs

    @action(detail=False, methods=['post'])
    def issue(self, request):
        user_id = request.data.get('user_id')
        book_ids = request.data.get('book_ids', [])
        try:
            user = User.objects.get(id=user_id, school=request.user.school)
        except User.DoesNotExist:
            return Response({'error': 'Пользователь не найден в вашей школе'}, status=status.HTTP_404_NOT_FOUND)
        loans = issue_books(request.user.school, user, book_ids, request.user)
        return Response(RegularBookLoanSerializer(loans, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def return_books(self, request):
        loan_ids = request.data.get('loan_ids', [])
        forced = request.data.get('forced', False)
        loans = return_books_service(loan_ids, forced)
        return Response(RegularBookLoanSerializer(loans, many=True).data)

    @action(detail=False, methods=['post'])
    def qr_token(self, request):
        user_id = request.data.get('user_id') or str(request.user.id)
        book_ids = request.data.get('book_ids', [])
        token = create_issue_token(request.user.school_id, str(user_id), book_ids)
        return Response({'token': token})

    @action(detail=False, methods=['post'])
    def scan_qr(self, request):
        token = request.data.get('token', '')
        loans, error = process_qr_issue(token, request.user)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        from apps.loans.serializers import TextbookLoanSerializer
        data = []
        for loan in loans:
            if hasattr(loan, 'textbook_id'):
                data.append(TextbookLoanSerializer(loan).data)
            else:
                data.append(RegularBookLoanSerializer(loan).data)
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def process_return(self, request):
        token = request.data.get('token', '')
        loans, error = process_qr_return(token, request.user)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        from apps.loans.serializers import TextbookLoanSerializer
        data = []
        for loan in loans:
            if hasattr(loan, 'textbook_id'):
                data.append(TextbookLoanSerializer(loan).data)
            else:
                data.append(RegularBookLoanSerializer(loan).data)
        return Response({'message': 'Возврат выполнен', 'count': len(loans), 'loans': data})
