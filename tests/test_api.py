from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.schools.models import District, School, Class
from apps.catalog.models import RegularBook
from apps.accounts.services import create_user


class AuthAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.user, self.password = create_user(
            role=User.Role.STUDENT, first_name='Test', last_name='User',
            school=self.school,
        )

    def test_login_success(self):
        resp = self.client.post('/api/v1/auth/login/', {
            'login': self.user.login,
            'password': self.password,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)
        self.assertIn('user', resp.data)

    def test_login_failure(self):
        resp = self.client.post('/api/v1/auth/login/', {
            'login': self.user.login,
            'password': 'wrong_password',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_endpoint(self):
        resp = self.client.post('/api/v1/auth/login/', {
            'login': self.user.login,
            'password': self.password,
        }, format='json')
        token = resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp = self.client.get('/api/v1/auth/me/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['login'], self.user.login)


class SchoolAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.cls = Class.objects.create(
            number=5, parallel='A', language='ru',
            academic_year='2025-2026', school=self.school,
        )
        self.admin = User.objects.create_superuser(
            login='admin', password='admin123', school=self.school,
        )
        resp = self.client.post('/api/v1/auth/login/', {
            'login': 'admin', 'password': 'admin123',
        }, format='json')
        token = resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_list_districts(self):
        resp = self.client.get('/api/v1/districts/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_create_school(self):
        resp = self.client.post('/api/v1/schools/', {
            'name': 'New School',
            'district': str(self.district.id),
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(School.objects.count(), 2)

    def test_list_classes(self):
        resp = self.client.get('/api/v1/classes/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)


class CatalogAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.admin = User.objects.create_superuser(login='admin', password='admin123')
        resp = self.client.post('/api/v1/auth/login/', {
            'login': 'admin', 'password': 'admin123',
        }, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {resp.data["access"]}')

    def test_create_textbook(self):
        resp = self.client.post('/api/v1/textbooks/', {
            'title': 'Math', 'subject': 'Math', 'grade_number': 5,
            'language': 'ru', 'academic_year': '2025-2026',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_categories(self):
        resp = self.client.get('/api/v1/categories/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class LoanAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.cls = Class.objects.create(
            number=5, parallel='A', language='ru',
            academic_year='2025-2026', school=self.school,
        )
        self.admin = User.objects.create_superuser(
            login='admin', password='admin123', school=self.school,
        )
        self.textbook = __import__('apps.catalog.models', fromlist=['Textbook']).Textbook.objects.create(
            title='Math', subject='Math', grade_number=5,
            language='ru', academic_year='2025-2026',
        )
        self.stock = __import__('apps.catalog.models', fromlist=['TextbookStock']).TextbookStock.objects.create(
            school=self.school, textbook=self.textbook, total_copies=5, available_copies=5,
        )
        resp = self.client.post('/api/v1/auth/login/', {
            'login': 'admin', 'password': 'admin123',
        }, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {resp.data["access"]}')
        self.student, _ = create_user(
            role=User.Role.STUDENT, first_name='Stud', last_name='Ent',
            school=self.school, grade=self.cls,
        )

    def test_issue_textbook(self):
        resp = self.client.post('/api/v1/textbook-loans/issue/', {
            'student_id': str(self.student.id),
            'textbook_ids': [str(self.textbook.id)],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        if isinstance(resp.data, dict):
            self.assertIn('loans', resp.data)
            self.assertEqual(len(resp.data['loans']), 1)
        else:
            self.assertEqual(len(resp.data), 1)

    def test_issue_textbook_no_stock(self):
        self.stock.available_copies = 0
        self.stock.save()
        resp = self.client.post('/api/v1/textbook-loans/issue/', {
            'student_id': str(self.student.id),
            'textbook_ids': [str(self.textbook.id)],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.data['loans']), 0)
        self.assertEqual(len(resp.data['skipped']), 1)
        self.assertEqual(resp.data['skipped'][0]['reason'], 'no_stock')

    def test_list_loans(self):
        resp = self.client.get('/api/v1/textbook-loans/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class QRTokenTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.admin, self.admin_pwd = create_user(
            role=User.Role.SCHOOL_ADMIN, first_name='Admin', last_name='User',
            school=self.school,
        )
        self.student, self.student_pwd = create_user(
            role=User.Role.STUDENT, first_name='Student', last_name='User',
            school=self.school,
        )
        self.book = RegularBook.objects.create(
            title='Test Book', author='Author', school=self.school,
            total_copies=3, available_copies=3,
        )

    def test_qr_token_generate_and_validate(self):
        from apps.loans.services import generate_qr_token, validate_qr_token
        payload = {'school_id': str(self.school.id), 'user_id': str(self.student.id), 'book_ids': [str(self.book.id)]}
        token = generate_qr_token(payload, ttl_seconds=120)
        self.assertIn('.', token)
        result = validate_qr_token(token)
        self.assertIsNotNone(result)
        self.assertEqual(result['school_id'], str(self.school.id))

    def test_qr_token_expired(self):
        from apps.loans.services import generate_qr_token, validate_qr_token
        payload = {'school_id': str(self.school.id), 'user_id': str(self.student.id), 'book_ids': []}
        token = generate_qr_token(payload, ttl_seconds=-1)
        result = validate_qr_token(token)
        self.assertIsNone(result)

    def test_qr_token_invalid(self):
        from apps.loans.services import validate_qr_token
        result = validate_qr_token('invalid.token.here')
        self.assertIsNone(result)

    def test_create_issue_token(self):
        from apps.loans.services import create_issue_token
        token = create_issue_token(self.school.id, str(self.student.id), [str(self.book.id)])
        self.assertTrue(token)

    def test_student_cannot_access_other_school_challenge(self):
        from apps.gamification.models import Challenge
        other_school = School.objects.create(name='Other School', district=self.district)
        other_student, other_pwd = create_user(
            role=User.Role.STUDENT, first_name='Other', last_name='Student',
            school=other_school,
        )
        challenge = Challenge.objects.create(
            grade_number=5, language='ru',
            week_start='2025-01-01',
            school=other_school, status=Challenge.Status.PUBLISHED,
            questions=[{'question': 'Q', 'options': ['A', 'B', 'C'], 'correct_index': 0}] * 15,
        )
        resp = self.client.post('/api/v1/auth/login/', {
            'login': self.student.login, 'password': self.student_pwd,
        }, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {resp.data["access"]}')
        resp = self.client.post('/api/v1/challenge-attempts/start/', {
            'challenge_id': str(challenge.id),
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
