from django.test import TestCase

from apps.accounts.models import User
from apps.schools.models import District, School, Class
from apps.catalog.models import Category, Textbook, TextbookStock, RegularBook
from apps.loans.models import TextbookLoan, RegularBookLoan
from apps.gamification.models import Achievement, Level
from apps.accounts.services import create_user, generate_password


class UserModelTest(TestCase):
    def setUp(self):
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)

    def test_create_superuser(self):
        user = User.objects.create_superuser(login='admin', password='admin123')
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.role, 'superadmin')

    def test_create_student(self):
        user, pwd = create_user(
            role=User.Role.STUDENT, first_name='John', last_name='Doe',
            school=self.school,
        )
        self.assertEqual(user.role, 'student')
        self.assertEqual(user.school, self.school)
        self.assertTrue(pwd)

    def test_create_teacher(self):
        user, pwd = create_user(
            role=User.Role.TEACHER, first_name='Jane', last_name='Smith',
            school=self.school, subject='Math',
        )
        self.assertEqual(user.role, 'teacher')
        self.assertEqual(user.subject, 'Math')


class SchoolModelTest(TestCase):
    def setUp(self):
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.cls = Class.objects.create(
            number=5, parallel='A', language='ru', academic_year='2025-2026',
            school=self.school,
        )

    def test_district_str(self):
        self.assertEqual(str(self.district), 'Test District')

    def test_school_str(self):
        self.assertIn('Test School', str(self.school))

    def test_class_str(self):
        self.assertIn('5A', str(self.cls))


class CatalogModelTest(TestCase):
    def setUp(self):
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.category = Category.objects.create(name='Fiction')
        self.textbook = Textbook.objects.create(
            title='Math 5', subject='Math', grade_number=5,
            language='ru', academic_year='2025-2026',
        )
        self.stock = TextbookStock.objects.create(
            school=self.school, textbook=self.textbook,
            total_copies=10, available_copies=10,
        )
        self.book = RegularBook.objects.create(
            school=self.school, title='War and Peace',
            author='Tolstoy', category=self.category,
            total_copies=3, available_copies=3,
        )

    def test_textbook_str(self):
        self.assertIn('Math 5', str(self.textbook))

    def test_textbook_stock(self):
        self.assertEqual(self.stock.available_copies, 10)

    def test_regular_book(self):
        self.assertEqual(self.book.available_copies, 3)


class LoanModelTest(TestCase):
    def setUp(self):
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.textbook = Textbook.objects.create(
            title='Math 5', subject='Math', grade_number=5,
            language='ru', academic_year='2025-2026',
        )
        self.stock = TextbookStock.objects.create(
            school=self.school, textbook=self.textbook,
            total_copies=5, available_copies=5,
        )
        self.student, _ = create_user(
            role=User.Role.STUDENT, first_name='Student', last_name='Test',
            school=self.school,
        )

    def test_textbook_loan(self):
        from apps.loans.services import issue_textbooks, return_textbooks
        loans, skipped = issue_textbooks(self.school, self.student, [self.textbook.id], self.student)
        self.assertEqual(len(loans), 1)
        self.assertEqual(len(skipped), 0)
        self.assertEqual(loans[0].status, 'active')
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.available_copies, 4)
        return_textbooks([loans[0].id], self.student)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.available_copies, 5)


class GamificationTest(TestCase):
    def test_level_exists(self):
        self.assertGreaterEqual(Level.objects.count(), 10)

    def test_new_achievement(self):
        count_before = Achievement.objects.count()
        Achievement.objects.create(
            code='test_ach', name='Test', description='Test',
            icon_emoji='🎯', category='xp',
        )
        self.assertEqual(Achievement.objects.count(), count_before + 1)

    def test_level_up(self):
        from apps.gamification.services import add_xp, ensure_levels
        from apps.gamification.models import UserLevel
        ensure_levels()

        district = District.objects.create(name='Test District')
        school = School.objects.create(name='Test School', district=district)
        student, _ = create_user(
            role=User.Role.STUDENT, first_name='Level', last_name='Up',
            school=school,
        )
        student.is_active_for_gamification = True
        student.save()

        ul, _ = UserLevel.objects.get_or_create(user=student, defaults={'level': Level.objects.get(number=1), 'total_xp': 0})
        self.assertEqual(ul.level.number, 1)

        # Add 500 XP (should reach Level 4, which needs 500 XP)
        add_xp(student, 500, 'test')
        ul.refresh_from_db()
        self.assertEqual(ul.level.number, 4)

        # Add another 1000 XP -> total 1500 XP (should reach Level 5, which needs 1000 XP)
        add_xp(student, 1000, 'test')
        ul.refresh_from_db()
        self.assertEqual(ul.level.number, 5)

    def test_gamification_disabled(self):
        from apps.gamification.services import add_xp
        from apps.gamification.models import UserLevel

        district = District.objects.create(name='Test District')
        school = School.objects.create(name='Test School', district=district)
        student, _ = create_user(
            role=User.Role.STUDENT, first_name='No', last_name='Gamification',
            school=school,
        )

        add_xp(student, 500, 'test')
        self.assertFalse(UserLevel.objects.filter(user=student).exists())


class NotificationTest(TestCase):
    def setUp(self):
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.admin, _ = create_user(
            role=User.Role.SCHOOL_ADMIN, first_name='Admin', last_name='User',
            school=self.school,
        )
        self.student, _ = create_user(
            role=User.Role.STUDENT, first_name='Student', last_name='User',
            school=self.school,
        )

    def test_news_visible_to_school_admin(self):
        from apps.notifications.models import News
        from apps.notifications.services import NewsService
        school_news = News.objects.create(
            title='School News', content='Content',
            author=self.admin, author_level='school_admin',
            school=self.school, is_published=True,
        )
        global_news = News.objects.create(
            title='Global News', content='Content',
            author=self.admin, author_level='superadmin',
            school=None, is_published=True,
        )
        visible = NewsService.visible_to(self.admin)
        self.assertIn(school_news, visible)
        self.assertIn(global_news, visible)

    def test_news_not_visible_to_other_school(self):
        from apps.notifications.models import News
        from apps.notifications.services import NewsService
        other_school = School.objects.create(name='Other School', district=self.district)
        other_admin, _ = create_user(
            role=User.Role.SCHOOL_ADMIN, first_name='Other', last_name='Admin',
            school=other_school,
        )
        school_news = News.objects.create(
            title='School News', content='Content',
            author=self.admin, author_level='school_admin',
            school=self.school, is_published=True,
        )
        visible = NewsService.visible_to(other_admin)
        self.assertNotIn(school_news, visible)


class ComebackBonusTest(TestCase):
    def setUp(self):
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.student, _ = create_user(
            role=User.Role.STUDENT, first_name='Student', last_name='User',
            school=self.school,
        )
        self.student.is_active_for_gamification = True
        self.student.save()

    def test_comeback_bonus_awarded(self):
        from apps.gamification.services import award_comeback_bonus
        from apps.gamification.models import XPTransaction
        from apps.loans.models import TextbookLoan, Textbook
        textbook = Textbook.objects.create(
            title='Test', subject='Test', grade_number=5,
            language='ru', academic_year='2025-2026',
        )
        TextbookLoan.objects.create(
            textbook=textbook, student=self.student,
            issued_by=self.student, due_date='2025-01-01',
            status=TextbookLoan.Status.OVERDUE, school=self.school,
        )
        XPTransaction.objects.create(
            user=self.student, amount=10,
            reason=XPTransaction.Reason.RETURN_LATE, school=self.school,
        )
        tx = award_comeback_bonus(self.student)
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 30)

    def test_comeback_bonus_not_without_late(self):
        from apps.gamification.services import award_comeback_bonus
        tx = award_comeback_bonus(self.student)
        self.assertIsNone(tx)
