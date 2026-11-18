from django.urls import path
from . import views

urlpatterns = [
    # 5 Staff Tutors Portal
    path('staff/', views.staff_dashboard_view, name='staff_dashboard'),
    path('staff/assign-homework/', views.staff_assign_homework, name='staff_assign_homework'),
    path('staff/grade-homework/<int:sub_id>/', views.staff_grade_homework, name='staff_grade_homework'),
    path('staff/create-quiz/', views.staff_create_quiz, name='staff_create_quiz'),
    path('staff/update-attendance/', views.staff_update_attendance, name='staff_update_attendance'),
    path('staff/update-marks/', views.staff_update_marks, name='staff_update_marks'),
    path('staff/schedule-meet/', views.staff_schedule_meet, name='staff_schedule_meet'),
    path('staff/library-reply/<int:thread_id>/', views.staff_library_reply, name='staff_library_reply'),
    path('staff/line-chat/', views.faculty_line_chat_view, name='faculty_line_chat'),

    # 1 HOD Portal (Notices, Tutors Data Oversight, CSV Report Downloads)
    path('hod/', views.hod_dashboard_view, name='hod_dashboard'),
    path('hod/post-notice/', views.hod_post_notice, name='hod_post_notice'),
    path('hod/delete-notice/<int:notice_id>/', views.hod_delete_notice, name='hod_delete_notice'),
    path('hod/tutor/<int:tutor_id>/', views.hod_tutor_detail_view, name='hod_tutor_detail'),
    path('hod/reports/<str:report_type>/', views.hod_download_report, name='hod_download_report'),
]
