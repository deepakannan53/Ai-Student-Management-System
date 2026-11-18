from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.student_login_view, name='student_login'),
    path('logout/', views.student_logout_view, name='student_logout'),

    # 1. Overall Dashboard
    path('', views.dashboard_view, name='dashboard'),
    path('widgets/<int:widget_id>/toggle/', views.toggle_widget_pin, name='toggle_widget_pin'),

    # 2. Profile
    path('profile/', views.profile_view, name='profile'),

    # 3. Assessments / Online Quiz with Rules
    path('assessments/', views.assessments_list_view, name='assessments'),
    path('assessments/<int:quiz_id>/attempt/', views.take_quiz_view, name='take_quiz'),

    # 4. Homework
    path('homework/', views.homework_view, name='homework'),

    # 5. Attendance & Marks
    path('academics/', views.attendance_marks_view, name='academics'),

    # 6. AI-Agentic SMTP Mail Module
    path('mail/', views.mail_hub_view, name='mail_hub'),
    path('mail/ai-draft/', views.ai_draft_mail_api, name='ai_draft_mail_api'),
    path('mail/simulate-inbound/', views.simulate_inbound_mail, name='simulate_inbound_mail'),

    # 7. Fees Payment & Receipt Download
    path('fees/', views.fees_view, name='fees'),
    path('fees/<int:fee_id>/pay/', views.pay_fee_view, name='pay_fee'),
    path('fees/<int:fee_id>/receipt/', views.download_fee_receipt, name='download_receipt'),

    # 8. LINE AI Agent & Nothing Essential Key
    path('line/', views.line_agent_view, name='line_agent'),
    path('essential-key/capture/', views.essential_key_capture, name='essential_key_capture'),

    # 9. Google Meet Integration
    path('meet/', views.google_meet_view, name='google_meet'),

    # 10. Library Requesting Chatbox (Student <-> Tutors)
    path('library/', views.library_chat_view, name='library_chat'),

    # 11. Notice Board
    path('notices/', views.notice_board_view, name='notices'),

    # 12. Student Settings
    path('settings/', views.student_settings_view, name='settings'),
    path('toggle-theme/', views.toggle_theme_view, name='toggle_theme'),
]
