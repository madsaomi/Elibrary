from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import User
from apps.accounts.managers import UserManager
from apps.schools.models import District, School, Class, TransferLog
from apps.catalog.models import Textbook, TextbookStock, RegularBook, Category
from apps.loans.models import TextbookLoan, RegularBookLoan
from apps.gamification.models import Level, UserLevel, Challenge, ChallengeAttempt, Streak, XPTransaction
from apps.accounts.services import create_user, generate_login, generate_password
from apps.schools.transfer_service import initiate_departure, complete_departure, accept_transfer, cancel_transfer
from apps.loans.services import (
    issue_textbooks, return_textbooks, issue_books, return_books,
    get_student_textbook_set, generate_qr_token, validate_qr_token,
)
from apps.gamification.services import add_xp, ensure_levels, update_streak, award_comeback_bonus
from apps.catalog.services import create_regular_book


class BugFix1TransferLogToSchoolTest(TestCase):
    """Bug #1: TransferLog.to_school was NOT NULL, causing IntegrityError"""

    def test_initiate_departure_creates_log(self):
        district = District.objects.create(name='D1')
        school = School.objects.create(name='S1', district=district)
        student, _ = create_user(role=User.Role.STUDENT, first_name='A', last_name='B', school=school)
        admin, _ = create_user(role=User.Role.SCHOOL_ADMIN, first_name='Admin', last_name='User', school=school)

        transfer, error = initiate_departure(student, admin)
        self.assertIsNone(error)
        self.assertIsNotNone(transfer)
        self.assertIsNone(transfer.to_school)
        self.assertEqual(transfer.status, TransferLog.Status.DEPARTING)


class BugFix2AcceptTransferTest(TestCase):
    """Bug #2: accept_transfer read user.school (None) instead of transfer.from_school"""

    def setUp(self):
        self.d1 = District.objects.create(name='D1')
        self.school1 = School.objects.create(name='S1', district=self.d1)
        self.school2 = School.objects.create(name='S2', district=self.d1)
        self.student, _ = create_user(role=User.Role.STUDENT, first_name='X', last_name='Y', school=self.school1)
        self.admin1, _ = create_user(role=User.Role.SCHOOL_ADMIN, first_name='A1', last_name='B1', school=self.school1)
        self.admin2, _ = create_user(role=User.Role.SCHOOL_ADMIN, first_name='A2', last_name='B2', school=self.school2)

    def test_loans_transfer_to_new_school(self):
        textbook = Textbook.objects.create(title='T1', subject='Math', grade_number=5, language='ru', academic_year='2025-2026')
        TextbookStock.objects.create(school=self.school1, textbook=textbook, total_copies=5, available_copies=4)
        loan = TextbookLoan.objects.create(
            school=self.school1, textbook=textbook, student=self.student,
            issued_by=self.admin1, due_date=timezone.now().date() + timedelta(days=365),
        )

        initiate_departure(self.student, self.admin1)
        complete_departure(self.student.id, self.admin1)
        accept_transfer(self.student.id, self.school2, self.admin2)

        loan.refresh_from_db()
        self.assertEqual(loan.school_id, self.school2.id)


class BugFix3CancelTransferTest(TestCase):
    """Bug #3: cancel_transfer didn't restore school/grade"""

    def test_cancel_restores_school_and_grade(self):
        d = District.objects.create(name='D1')
        school = School.objects.create(name='S1', district=d)
        cls = Class.objects.create(number=5, parallel='A', language='ru', academic_year='2025-2026', school=school)
        student, _ = create_user(role=User.Role.STUDENT, first_name='C', last_name='D', school=school)
        student.grade = cls
        student.save()
        admin, _ = create_user(role=User.Role.SCHOOL_ADMIN, first_name='A', last_name='B', school=school)

        initiate_departure(student, admin)
        complete_departure(student.id, admin)

        self.assertIsNone(student.school)
        self.assertIsNone(student.grade)

        cancel_transfer(student.id)
        student.refresh_from_db()
        self.assertEqual(student.school, school)
        self.assertEqual(student.grade, cls)


class BugFix4ChallengeKeyMismatchTest(TestCase):
    """Bug #4: AI generates 'correct_index', views check for 'correct'"""

    def test_start_accepts_correct_index(self):
        d = District.objects.create(name='D1')
        school = School.objects.create(name='S1', district=d)
        student, _ = create_user(role=User.Role.STUDENT, first_name='Q', last_name='W', school=school)
        student.is_active_for_gamification = True
        student.save()
        ensure_levels()

        challenge = Challenge.objects.create(
            school=school, grade_number=5, language='ru',
            week_start=timezone.now().date(),
            questions=[
                {'question': 'Q1', 'options': ['A', 'B', 'C'], 'correct_index': 0},
                {'question': 'Q2', 'options': ['A', 'B', 'C'], 'correct_index': 1},
            ],
            status=Challenge.Status.PUBLISHED,
        )

        from rest_framework.test import APIRequestFactory
        from apps.gamification.views import ChallengeAttemptViewSet
        factory = APIRequestFactory()
        request = factory.post('/start/', {'challenge_id': str(challenge.id)}, format='json')
        request.user = student
        view = ChallengeAttemptViewSet.as_view({'post': 'start'})
        response = view(request)
        self.assertEqual(response.status_code, 200)


class BugFix5ClassPromotionTest(TestCase):
    """Bug #5: auto_promote_classes marked old classes as ACTIVE instead of GRADUATED"""

    def test_old_class_marked_graduated(self):
        from apps.schools.services import auto_promote_classes
        d = District.objects.create(name='D1')
        school = School.objects.create(name='S1', district=d)
        cls = Class.objects.create(number=5, parallel='A', language='ru', academic_year='2025-2026', school=school)

        auto_promote_classes(school, '2025-2026', '2026-2027')
        cls.refresh_from_db()
        self.assertEqual(cls.status, Class.Status.GRADUATED)


class BugFix6PrivilegeEscalationTest(TestCase):
    """Bug #6: create_user accepted is_superuser in extra_fields"""

    def test_create_user_blocks_superuser(self):
        user = User.objects.create_user(
            login='hacker', password='pass123',
            is_superuser=True, is_staff=True,
            role='student',
        )
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)


class BugFix7PermissionsTest(TestCase):
    """Bugs #7-9: ViewSets without permission_classes"""

    def setUp(self):
        self.d = District.objects.create(name='D1')
        self.school = School.objects.create(name='S1', district=self.d)
        self.student, _ = create_user(role=User.Role.STUDENT, first_name='S', last_name='T', school=self.school)
        self.student.is_active_for_gamification = True
        self.student.save()
        ensure_levels()

    def test_student_cannot_create_challenge(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.student)
        response = client.post('/api/v1/challenges/', {'grade_number': 5}, format='json')
        self.assertIn(response.status_code, [403, 405])

    def test_student_cannot_create_news(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.student)
        response = client.post('/api/v1/news/', {'title': 'Test', 'content': 'Test'}, format='json')
        self.assertIn(response.status_code, [403, 405])


class BugFix10RaceConditionTest(TestCase):
    """Bug #10: issue_textbooks_to_class missing select_for_update"""

    def test_stock_decremented_atomically(self):
        d = District.objects.create(name='D1')
        school = School.objects.create(name='S1', district=d)
        cls = Class.objects.create(number=5, parallel='A', language='ru', academic_year='2025-2026', school=school)
        textbook = Textbook.objects.create(title='T', subject='M', grade_number=5, language='ru', academic_year='2025-2026')
        stock = TextbookStock.objects.create(school=school, textbook=textbook, total_copies=2, available_copies=2)
        admin, _ = create_user(role=User.Role.SCHOOL_ADMIN, first_name='A', last_name='B', school=school)

        s1, _ = create_user(role=User.Role.STUDENT, first_name='S1', last_name='X', school=school, grade=cls)
        s2, _ = create_user(role=User.Role.STUDENT, first_name='S2', last_name='Y', school=school, grade=cls)

        from apps.loans.services import issue_textbooks_to_class
        loans = issue_textbooks_to_class(school, cls, admin)
        stock.refresh_from_db()
        self.assertEqual(len(loans), 2)
        self.assertEqual(stock.available_copies, 0)


class BugFix11LogoutCSRFCrossSiteTest(TestCase):
    """Bug #11: logout_form_view accepted GET"""

    def test_logout_requires_post(self):
        from django.test import Client
        client = Client()
        response = client.get('/accounts/logout/')
        self.assertIn(response.status_code, [405, 302])


class BugFix15QRTokenNoMutationTest(TestCase):
    """Bug: generate_qr_token mutated input payload"""

    def test_payload_not_mutated(self):
        payload = {'school_id': '123', 'user_id': '456'}
        original_keys = set(payload.keys())
        generate_qr_token(payload)
        self.assertEqual(set(payload.keys()), original_keys)


class BugFix16ReturnBooksOverdueTest(TestCase):
    """Bug: return_books always awarded 30 XP regardless of due_date"""

    def test_overdue_book_awards_half_xp(self):
        d = District.objects.create(name='D1')
        school = School.objects.create(name='S1', district=d)
        cat = Category.objects.create(name='Fiction')
        book = RegularBook.objects.create(school=school, title='B', author='A', category=cat, total_copies=1, available_copies=0)
        student, _ = create_user(role=User.Role.STUDENT, first_name='O', last_name='P', school=school)
        student.is_active_for_gamification = True
        student.save()
        ensure_levels()

        loan = RegularBookLoan.objects.create(
            school=school, book=book, user=student,
            due_date=timezone.now().date() - timedelta(days=5),
        )

        return_books([loan.id])
        tx = XPTransaction.objects.filter(user=student, reason='return_late').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 15)


class BugFix17NPlusOneTest(TestCase):
    """Bug: get_student_textbook_set had N+1 queries"""

    def test_batch_queries(self):
        d = District.objects.create(name='D1')
        school = School.objects.create(name='S1', district=d)
        cls = Class.objects.create(number=5, parallel='A', language='ru', academic_year='2025-2026', school=school)
        student, _ = create_user(role=User.Role.STUDENT, first_name='N', last_name='P', school=school, grade=cls)

        t1 = Textbook.objects.create(title='T1', subject='M', grade_number=5, language='ru', academic_year='2025-2026')
        t2 = Textbook.objects.create(title='T2', subject='R', grade_number=5, language='ru', academic_year='2025-2026')
        from apps.catalog.models import SubjectTextbook
        SubjectTextbook.objects.create(school_class=cls, textbook=t1, subject='M')
        SubjectTextbook.objects.create(school_class=cls, textbook=t2, subject='R')

        with self.assertNumQueries(2):
            result = get_student_textbook_set(student)
        self.assertEqual(len(result), 2)


class BugFix18DeduplicationTest(TestCase):
    """Bug: create_regular_book didn't deduplicate"""

    def test_same_book_not_duplicated(self):
        d = District.objects.create(name='D1')
        school = School.objects.create(name='S1', district=d)
        cat = Category.objects.create(name='F')

        b1, created1 = create_regular_book(school, 'Book', 'Author', cat, 2)
        b2, created2 = create_regular_book(school, 'Book', 'Author', cat, 3)

        self.assertTrue(created1)
        self.assertFalse(created2)
        b1.refresh_from_db()
        self.assertEqual(b1.total_copies, 5)
        self.assertEqual(b1.available_copies, 5)
