# Auto-reexport all view functions for backward compatibility with urls.py
from dashboard.views.home import home
from dashboard.views.profile import profile, edit_profile, change_password, award_freeze_view
from dashboard.views.users import (
    users_list, student_detail, reset_password_view, activate_grade_5_view,
    import_csv_view, import_teachers_csv, manage_young_students, homeroom_dashboard,
)
from dashboard.views.catalog import (
    textbooks_list, textbook_create, textbook_stock_view, textbook_detail,
    books_list, book_create, book_detail,
    student_catalog, add_to_cart, remove_from_cart, cart_counter_fragment,
    student_textbook_cart, manage_subject_textbooks,
)
from dashboard.views.loans import (
    issue_textbooks_view, issue_textbooks_set_view, return_textbooks_view,
    teacher_borrow_textbook, teacher_books_view, multi_class_teacher_borrow,
    my_loans, bulk_issue_to_class, export_students,
)
from dashboard.views.qr import (
    qr_scanner, cart, qr_return_view, textbook_qr_return_view,
    qr_issue, qr_issue_refresh, qr_return_loans,
)
from dashboard.views.schools import (
    manage_classes, class_add_student, class_remove_student, class_transfer_student,
    manage_districts, manage_schools, manage_admins,
    school_settings, promote_classes_view,
    transfers_list, transfer_depart, transfer_accept,
)
from dashboard.views.challenges import (
    challenge_leaderboard, student_challenge,
    challenge_moderation, challenge_moderation_detail,
)
from dashboard.views.news import news_list, news_create
from dashboard.views.stats import superadmin_dashboard, inventory, return_list_export
from dashboard.views.notifications import notification_badge, notification_list, mark_notifications_read
