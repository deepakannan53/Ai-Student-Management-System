from django.contrib import admin
from .models import (
    StudentProfile, Tutor, Subject, AttendanceRecord, InternalMark,
    OnlineQuiz, QuizQuestion, QuizAttempt, Homework, HomeworkSubmission,
    StudentMail, FeeRecord, EssentialNote, DynamicDashboardWidget,
    LineChatMessage, GoogleMeetSession, LibraryRequestThread, LibraryChatMessage, Notice
)

admin.site.register([
    StudentProfile, Tutor, Subject, AttendanceRecord, InternalMark,
    OnlineQuiz, QuizQuestion, QuizAttempt, Homework, HomeworkSubmission,
    StudentMail, FeeRecord, EssentialNote, DynamicDashboardWidget,
    LineChatMessage, GoogleMeetSession, LibraryRequestThread, LibraryChatMessage, Notice
])
