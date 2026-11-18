import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    roll_no = models.CharField(max_length=30, unique=True)
    register_no = models.CharField(max_length=30, unique=True)
    department = models.CharField(max_length=100, default="Computer Applications (MCA)")
    semester = models.PositiveSmallIntegerField(default=1)
    section = models.CharField(max_length=10, default="A")
    phone = models.CharField(max_length=20, blank=True)
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    avatar_initials = models.CharField(max_length=4, default="ST")

    college_email = models.EmailField()
    smtp_app_password = models.CharField(max_length=255, blank=True)

    theme_mode = models.CharField(
        max_length=10,
        choices=[('DARK', 'Nothing Matte Black'), ('LIGHT', 'Nothing Stark White')],
        default='DARK'
    )
    glyph_alerts_enabled = models.BooleanField(default=True)
    essential_key_shortcut = models.CharField(max_length=20, default="Alt+E")
    auto_triage_mail = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.roll_no} - {self.user.get_full_name() or self.user.username}"


class Tutor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='tutor_profile')
    staff_code = models.CharField(max_length=20, default="STF001")
    name = models.CharField(max_length=100)
    email = models.EmailField()
    department = models.CharField(max_length=100, default="Computer Applications (MCA)")
    designation = models.CharField(max_length=100, default="Assistant Professor")
    is_hod = models.BooleanField(default=False)
    theme_mode = models.CharField(
        max_length=10,
        choices=[('DARK', 'Nothing Matte Black'), ('LIGHT', 'Nothing Stark White')],
        default='DARK'
    )

    def __str__(self):
        role = "HOD" if self.is_hod else "STAFF"
        return f"[{role}] {self.name} ({self.email})"


class Subject(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    semester = models.PositiveSmallIntegerField(default=1)
    credits = models.PositiveSmallIntegerField(default=4)
    tutor = models.ForeignKey(Tutor, on_delete=models.SET_NULL, null=True, related_name='subjects')

    def __str__(self):
        return f"{self.code} - {self.name}"


class AttendanceRecord(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='attendance')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    total_classes = models.PositiveIntegerField(default=0)
    attended_classes = models.PositiveIntegerField(default=0)

    @property
    def percentage(self):
        if self.total_classes == 0:
            return 100.0
        return round((self.attended_classes / self.total_classes) * 100, 1)

    @property
    def is_low(self):
        return self.percentage < 75.0

    @property
    def safe_bunk_or_recovery(self):
        if self.total_classes == 0:
            return "No classes logged yet"
        if self.percentage >= 75.0:
            can_miss = int((self.attended_classes / 0.75) - self.total_classes)
            return f"Safe margin: can miss {max(0, can_miss)} class(es)"
        need = int(((0.75 * self.total_classes) - self.attended_classes) / 0.25) + 1
        return f"Alert: attend next {need} consecutive class(es)"


class InternalMark(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='marks')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    cia_1 = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cia_2 = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    model_exam = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    assignment_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    @property
    def total_internal(self):
        return round(float(self.cia_1 + self.cia_2 + self.model_exam + self.assignment_marks), 1)


class OnlineQuiz(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    duration_minutes = models.PositiveIntegerField(default=20)
    total_marks = models.PositiveIntegerField(default=20)
    max_tab_switches = models.PositiveIntegerField(default=2)
    require_fullscreen = models.BooleanField(default=True)
    rules_text = models.TextField(
        default="1. Do not switch browser tabs or minimize the window.\n"
                "2. Fullscreen mode is mandatory throughout the attempt.\n"
                "3. Quiz auto-submits when the countdown hits 00:00 or tab-switch limit is breached.\n"
                "4. Only one attempt is permitted per student."
    )
    deadline = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.subject.code}: {self.title}"


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(OnlineQuiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')])
    marks = models.PositiveIntegerField(default=1)


class QuizAttempt(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(OnlineQuiz, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.IntegerField(default=0)
    tab_violations = models.PositiveIntegerField(default=0)
    auto_submitted_reason = models.CharField(max_length=100, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'quiz')


class Homework(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='homeworks')
    title = models.CharField(max_length=200)
    description = models.TextField()
    assigned_date = models.DateField(auto_now_add=True)
    due_date = models.DateTimeField()

    def __str__(self):
        return f"{self.subject.code} - {self.title}"


class HomeworkSubmission(models.Model):
    STATUS_CHOICES = [('PENDING', 'Pending'), ('SUBMITTED', 'Submitted'), ('GRADED', 'Graded')]
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    submission_text = models.TextField(blank=True)
    attachment = models.FileField(upload_to='homework_submissions/', blank=True, null=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    remarks = models.CharField(max_length=255, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)


class StudentMail(models.Model):
    CATEGORY_CHOICES = [
        ('staff', 'Staff'),
        ('notice', 'Notice'),
        ('placements', 'Placements'),
        ('competition', 'Competition'),
        ('others', 'Others'),
    ]
    DIRECTION_CHOICES = [('INBOUND', 'Inbound'), ('OUTBOUND', 'Outbound')]

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='mails')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='INBOUND')
    sender_name = models.CharField(max_length=120)
    sender_email = models.EmailField()
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='others')
    ai_summary = models.CharField(max_length=255, blank=True)
    extracted_deadline = models.CharField(max_length=100, blank=True)
    is_urgent = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    sent_via_smtp = models.BooleanField(default=False)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']


class FeeRecord(models.Model):
    STATUS_CHOICES = [('PAID', 'Paid'), ('PENDING', 'Pending'), ('OVERDUE', 'Overdue')]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='fees')
    semester = models.PositiveSmallIntegerField()
    fee_type = models.CharField(max_length=100, default="Tuition & Lab Fee")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    receipt_number = models.CharField(max_length=40, blank=True)
    paid_on = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=60, blank=True)

    def mark_paid(self):
        self.status = 'PAID'
        self.paid_on = timezone.now()
        self.receipt_number = f"NOS-RCP-{uuid.uuid4().hex[:8].upper()}"
        self.transaction_id = f"TXN{uuid.uuid4().hex[:10].upper()}"
        self.save()


class EssentialNote(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='essential_notes', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_essential_notes', null=True, blank=True)
    raw_input = models.TextField()
    ai_structured_action = models.CharField(max_length=255, blank=True)
    tag = models.CharField(max_length=30, default="STUDY")
    created_at = models.DateTimeField(auto_now_add=True)


class DynamicDashboardWidget(models.Model):
    WIDGET_TYPES = [
        ('STUDY_PLAN', 'Study Roadmap'),
        ('COUNTDOWN', 'Exam / Goal Countdown'),
        ('FORMULA_CARD', 'Quick Revision Card'),
        ('PROGRESS_TRACKER', 'Topic Checklist'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='dynamic_widgets')
    title = models.CharField(max_length=120)
    widget_type = models.CharField(max_length=25, choices=WIDGET_TYPES, default='STUDY_PLAN')
    accent_red = models.BooleanField(default=False)
    payload = models.JSONField(default=dict)
    is_pinned = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class LineChatMessage(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='line_chats', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_line_chats', null=True, blank=True)
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('assistant', 'LINE AI')])
    content = models.TextField()
    created_widget = models.ForeignKey(DynamicDashboardWidget, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class GoogleMeetSession(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='meetings')
    topic = models.CharField(max_length=200)
    meet_url = models.URLField()
    scheduled_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    is_live = models.BooleanField(default=True)


class LibraryRequestThread(models.Model):
    STATUS_CHOICES = [('OPEN', 'Open'), ('APPROVED', 'Approved / Issued'), ('CLOSED', 'Closed')]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='library_threads')
    tutor = models.ForeignKey(Tutor, on_delete=models.CASCADE, related_name='library_threads')
    book_or_resource_title = models.CharField(max_length=200)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='OPEN')
    updated_at = models.DateTimeField(auto_now=True)


class LibraryChatMessage(models.Model):
    thread = models.ForeignKey(LibraryRequestThread, on_delete=models.CASCADE, related_name='messages')
    sender_is_student = models.BooleanField(default=True)
    sender_name = models.CharField(max_length=100)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)


class Notice(models.Model):
    PRIORITY_CHOICES = [('NORMAL', 'Standard'), ('URGENT', 'Critical / Red Alert')]
    title = models.CharField(max_length=200)
    content = models.TextField()
    posted_by = models.CharField(max_length=100, default="Academic Office")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-posted_at']
