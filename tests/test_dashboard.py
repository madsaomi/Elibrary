from django.test import TestCase, Client, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.schools.models import District, School, Class
from apps.catalog.models import Textbook, RegularBook
from apps.notifications.models import News
from apps.accounts.services import create_user


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class DashboardAuthTest(TestCase):
    def setUp(self):
        self.client = Client()
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

    def test_home_requires_login(self):
        resp = self.client.get(reverse('dashboard:home'))
        self.assertEqual(resp.status_code, 302)

    def test_home_admin(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        resp = self.client.get(reverse('dashboard:home'))
        self.assertEqual(resp.status_code, 200)

    def test_home_student(self):
        self.client.login(username=self.student.login, password=self.student_pwd)
        resp = self.client.get(reverse('dashboard:home'))
        self.assertEqual(resp.status_code, 200)


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class TextbooksListTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.admin, self.admin_pwd = create_user(
            role=User.Role.SCHOOL_ADMIN, first_name='Admin', last_name='User',
            school=self.school,
        )
        self.textbook = Textbook.objects.create(
            title='Math 5', subject='Mathematics', grade_number=5,
            language='ru', academic_year='2025-2026',
        )

    def test_textbooks_list(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        resp = self.client.get(reverse('dashboard:textbooks'))
        self.assertEqual(resp.status_code, 200)

    def test_textbooks_search_by_title(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        resp = self.client.get(reverse('dashboard:textbooks'), {'q': 'Math'})
        self.assertEqual(resp.status_code, 200)

    def test_textbooks_search_by_subject(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        resp = self.client.get(reverse('dashboard:textbooks'), {'q': 'Mathematics'})
        self.assertEqual(resp.status_code, 200)

    def test_textbooks_search_by_academic_year(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        resp = self.client.get(reverse('dashboard:textbooks'), {'q': '2025'})
        self.assertEqual(resp.status_code, 200)


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class BooksListTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.admin, self.admin_pwd = create_user(
            role=User.Role.SCHOOL_ADMIN, first_name='Admin', last_name='User',
            school=self.school,
        )
        self.book = RegularBook.objects.create(
            title='Test Book', author='Author', school=self.school,
        )

    def test_books_list(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        resp = self.client.get(reverse('dashboard:books'))
        self.assertEqual(resp.status_code, 200)

    def test_books_search(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        resp = self.client.get(reverse('dashboard:books'), {'q': 'Test'})
        self.assertEqual(resp.status_code, 200)


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class ClassManagementTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.admin, self.admin_pwd = create_user(
            role=User.Role.SCHOOL_ADMIN, first_name='Admin', last_name='User',
            school=self.school,
        )
        self.cls = Class.objects.create(
            number=5, parallel='A', school=self.school,
            academic_year='2025-2026',
        )

    def test_classes_list(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        resp = self.client.get(reverse('dashboard:manage_classes'))
        self.assertEqual(resp.status_code, 200)

    def test_class_add_student_by_login(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        existing_student, _ = create_user(
            role=User.Role.STUDENT, first_name='Existing', last_name='Student',
            school=self.school,
        )
        resp = self.client.post(reverse('dashboard:class_add_student', args=[self.cls.id]), {
            'login': existing_student.login,
        })
        self.assertEqual(resp.status_code, 302)
        existing_student.refresh_from_db()
        self.assertEqual(existing_student.grade, self.cls)

    def test_class_add_student_new(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        resp = self.client.post(reverse('dashboard:class_add_student', args=[self.cls.id]), {
            'first_name': 'Тест',
            'last_name': 'Ученик',
        })
        self.assertEqual(resp.status_code, 302)
        new_user = User.objects.filter(role='student', school=self.school).exclude(id=self.admin.id).first()
        self.assertIsNotNone(new_user)
        self.assertTrue(new_user.login)
        self.assertTrue(new_user.has_usable_password())

    def test_class_remove_student(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        student, _ = create_user(
            role=User.Role.STUDENT, first_name='Remove', last_name='Me',
            school=self.school, grade=self.cls,
        )
        resp = self.client.post(reverse('dashboard:class_remove_student', args=[self.cls.id]), {
            'student_id': student.id,
        })
        self.assertEqual(resp.status_code, 302)
        student.refresh_from_db()
        self.assertIsNone(student.grade)


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class PasswordResetTest(TestCase):
    def setUp(self):
        self.client = Client()
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

    def test_reset_password(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        resp = self.client.post(reverse('dashboard:reset_password', args=[self.student.id]))
        self.assertEqual(resp.status_code, 200)
        self.student.refresh_from_db()
        self.assertFalse(self.client.login(username=self.student.login, password=self.student_pwd))


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class NewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.district = District.objects.create(name='Test District')
        self.school = School.objects.create(name='Test School', district=self.district)
        self.admin, self.admin_pwd = create_user(
            role=User.Role.SCHOOL_ADMIN, first_name='Admin', last_name='User',
            school=self.school,
        )
        self.superadmin = User.objects.create_superuser(login='superadmin', password='super123')

    def test_school_admin_news_auto_sets_school(self):
        self.client.login(username=self.admin.login, password=self.admin_pwd)
        resp = self.client.post(reverse('dashboard:news_create'), {
            'title': 'Test News',
            'content': 'Content',
            'is_published': '1',
        })
        self.assertEqual(resp.status_code, 302)
        news = News.objects.get(title='Test News')
        self.assertEqual(news.school, self.school)
        self.assertEqual(news.author, self.admin)

    def test_superadmin_news_has_no_school(self):
        self.client.login(username=self.superadmin.login, password='super123')
        resp = self.client.post(reverse('dashboard:news_create'), {
            'title': 'Global News',
            'content': 'Content',
            'is_published': '1',
        })
        self.assertEqual(resp.status_code, 302)
        news = News.objects.get(title='Global News')
        self.assertIsNone(news.school)
