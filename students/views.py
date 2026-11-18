import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    StudentProfile, Tutor, Subject, AttendanceRecord, InternalMark,
    OnlineQuiz, QuizAttempt, Homework, HomeworkSubmission,
    StudentMail, FeeRecord, EssentialNote, DynamicDashboardWidget,
    LineChatMessage, GoogleMeetSession, LibraryRequestThread, LibraryChatMessage, Notice
)
from .ai_agents import (
    classify_student_mail, draft_tutor_email,
    process_essential_key_capture, run_line_study_agent, get_ai_engine_status
)
from .mail_service import send_student_smtp_mail, sync_and_triage_inbox


def _get_student_profile(user):
    profile, _ = StudentProfile.objects.get_or_create(
        user=user,
        defaults={
            'roll_no': f"26MCA{user.id:03d}",
            'register_no': f"REG2026{user.id:04d}",
            'college_email': user.email or f"{user.username}@student.edu",
            'avatar_initials': (user.username[:2]).upper(),
        }
    )
    return profile


def _base_context(request, active_nav='dashboard'):
    profile = _get_student_profile(request.user)
    unread_mails = StudentMail.objects.filter(student=profile, direction='INBOUND', is_read=False).count()
    low_att_count = sum(1 for a in AttendanceRecord.objects.filter(student=profile) if a.is_low)
    pending_hw = HomeworkSubmission.objects.filter(student=profile, status='PENDING').count()
    essential_notes = EssentialNote.objects.filter(student=profile).order_by('-created_at')[:6]
    return {
        'profile': profile,
        'active_nav': active_nav,
        'unread_mails': unread_mails,
        'low_att_count': low_att_count,
        'pending_hw': pending_hw,
        'glyph_active': profile.glyph_alerts_enabled and (unread_mails > 0 or low_att_count > 0 or pending_hw > 0),
        'essential_notes': essential_notes,
        'ai_status': get_ai_engine_status(),
    }


def student_login_view(request):
    if request.user.is_authenticated:
        tutor = Tutor.objects.filter(user=request.user).first()
        if tutor:
            return redirect('hod_dashboard' if tutor.is_hod else 'staff_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            tutor = Tutor.objects.filter(user=user).first()
            if tutor:
                return redirect('hod_dashboard' if tutor.is_hod else 'staff_dashboard')
            return redirect('dashboard')
        messages.error(request, "Invalid credentials. Try student, hod, or staff1..staff5 (password: nothing123)")
    return render(request, 'students/login.html')


def student_logout_view(request):
    logout(request)
    return redirect('student_login')


# 1. OVERALL DASHBOARD
@login_required
def dashboard_view(request):
    tutor = Tutor.objects.filter(user=request.user).first()
    if tutor:
        return redirect('hod_dashboard' if tutor.is_hod else 'staff_dashboard')

    ctx = _base_context(request, 'dashboard')
    profile = ctx['profile']

    attendance_list = AttendanceRecord.objects.filter(student=profile).select_related('subject')
    avg_attendance = (
        round(sum(a.percentage for a in attendance_list) / len(attendance_list), 1)
        if attendance_list else 100.0
    )

    attempted_ids = QuizAttempt.objects.filter(student=profile, is_completed=True).values_list('quiz_id', flat=True)
    active_quizzes = OnlineQuiz.objects.filter(is_active=True).exclude(id__in=attempted_ids)[:3]
    pending_homeworks = HomeworkSubmission.objects.filter(student=profile, status='PENDING').select_related('homework__subject')[:3]
    recent_mails = StudentMail.objects.filter(student=profile, direction='INBOUND')[:4]
    live_meets = GoogleMeetSession.objects.filter(is_live=True).select_related('subject')[:2]
    notices = Notice.objects.all()[:3]
    dynamic_widgets = DynamicDashboardWidget.objects.filter(student=profile, is_pinned=True).order_by('-created_at')

    ctx.update({
        'avg_attendance': avg_attendance,
        'attendance_list': attendance_list,
        'active_quizzes': active_quizzes,
        'pending_homeworks': pending_homeworks,
        'recent_mails': recent_mails,
        'live_meets': live_meets,
        'notices': notices,
        'dynamic_widgets': dynamic_widgets,
    })
    return render(request, 'students/dashboard.html', ctx)


@login_required
@require_POST
def toggle_widget_pin(request, widget_id):
    profile = _get_student_profile(request.user)
    widget = get_object_or_404(DynamicDashboardWidget, id=widget_id, student=profile)
    widget.is_pinned = not widget.is_pinned
    widget.save()
    messages.success(request, f"Widget '{widget.title}' {'pinned to' if widget.is_pinned else 'unpinned from'} dashboard.")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


# 2. STUDENT PROFILE
@login_required
def profile_view(request):
    ctx = _base_context(request, 'profile')
    profile = ctx['profile']
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.save()
        profile.phone = request.POST.get('phone', profile.phone)
        profile.section = request.POST.get('section', profile.section)
        profile.college_email = request.POST.get('college_email', profile.college_email)
        profile.save()
        messages.success(request, "Student profile telemetry updated.")
        return redirect('profile')

    ctx['subjects'] = Subject.objects.filter(semester=profile.semester).select_related('tutor')
    return render(request, 'students/profile.html', ctx)


# 3. ONLINE ASSESSMENTS / QUIZ WITH STRICT RULES
@login_required
def assessments_list_view(request):
    ctx = _base_context(request, 'assessments')
    profile = ctx['profile']
    quizzes = OnlineQuiz.objects.filter(is_active=True).select_related('subject')
    attempts = {a.quiz_id: a for a in QuizAttempt.objects.filter(student=profile)}

    quiz_cards = [{'quiz': q, 'attempt': attempts.get(q.id)} for q in quizzes]
    ctx['quiz_cards'] = quiz_cards
    return render(request, 'students/assessments.html', ctx)


@login_required
def take_quiz_view(request, quiz_id):
    ctx = _base_context(request, 'assessments')
    profile = ctx['profile']
    quiz = get_object_or_404(OnlineQuiz, id=quiz_id, is_active=True)

    existing_attempt = QuizAttempt.objects.filter(student=profile, quiz=quiz, is_completed=True).first()
    if existing_attempt:
        messages.warning(request, "Rule Enforcement: Only one attempt is permitted per assessment.")
        return redirect('assessments')

    attempt, _ = QuizAttempt.objects.get_or_create(student=profile, quiz=quiz)

    if request.method == 'POST':
        score = 0
        for question in quiz.questions.all():
            chosen = request.POST.get(f"q_{question.id}", "")
            if chosen == question.correct_option:
                score += question.marks

        attempt.score = score
        attempt.tab_violations = int(request.POST.get('tab_violations', 0) or 0)
        attempt.auto_submitted_reason = request.POST.get('auto_submitted_reason', '')[:100]
        attempt.submitted_at = timezone.now()
        attempt.is_completed = True
        attempt.save()

        if attempt.auto_submitted_reason:
            messages.error(request, f"Assessment Auto-Submitted ({attempt.auto_submitted_reason}). Score: {score}/{quiz.total_marks}")
        else:
            messages.success(request, f"Assessment submitted cleanly! Score: {score}/{quiz.total_marks}")
        return redirect('assessments')

    ctx['quiz'] = quiz
    ctx['questions'] = quiz.questions.all()
    ctx['attempt'] = attempt
    return render(request, 'students/take_quiz.html', ctx)


# 4. HOMEWORK CHECKING & SUBMISSION
@login_required
def homework_view(request):
    ctx = _base_context(request, 'homework')
    profile = ctx['profile']

    if request.method == 'POST':
        hw_id = request.POST.get('homework_id')
        hw = get_object_or_404(Homework, id=hw_id)
        sub, _ = HomeworkSubmission.objects.get_or_create(homework=hw, student=profile)
        sub.submission_text = request.POST.get('submission_text', '')
        if 'attachment' in request.FILES:
            sub.attachment = request.FILES['attachment']
        sub.status = 'SUBMITTED'
        sub.submitted_at = timezone.now()
        sub.save()
        messages.success(request, f"Homework '{hw.title}' submitted successfully.")
        return redirect('homework')

    all_hw = Homework.objects.all().select_related('subject').order_by('due_date')
    items = []
    for hw in all_hw:
        sub, _ = HomeworkSubmission.objects.get_or_create(homework=hw, student=profile)
        items.append({'homework': hw, 'submission': sub})

    ctx['homework_items'] = items
    return render(request, 'students/homework.html', ctx)


# 5. ATTENDANCE & MARKS CHECKING
@login_required
def attendance_marks_view(request):
    ctx = _base_context(request, 'academics')
    profile = ctx['profile']
    ctx['attendance_records'] = AttendanceRecord.objects.filter(student=profile).select_related('subject')
    ctx['internal_marks'] = InternalMark.objects.filter(student=profile).select_related('subject')
    return render(request, 'students/academics.html', ctx)


# 6. AI-AGENTIC SMTP MAIL MODULE
@login_required
def mail_hub_view(request):
    ctx = _base_context(request, 'mail')
    profile = ctx['profile']

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'sync_imap':
            count = sync_and_triage_inbox(profile)
            messages.info(request, f"AI Mail Triage complete. Imported & sorted {count} new message(s).")
            return redirect('mail_hub')
        elif action == 'send_smtp':
            recipient = request.POST.get('recipient_email', '').strip()
            subject = request.POST.get('subject', '').strip()
            body = request.POST.get('body', '').strip()
            if recipient and subject and body:
                _, status_msg = send_student_smtp_mail(profile, recipient, subject, body, category='staff')
                messages.success(request, status_msg)
            else:
                messages.error(request, "Recipient, subject, and body are required.")
            return redirect('mail_hub')

    selected_cat = request.GET.get('cat', 'all')
    mails_qs = StudentMail.objects.filter(student=profile)

    if selected_cat == 'sent':
        mails = mails_qs.filter(direction='OUTBOUND')
    elif selected_cat in ['staff', 'notice', 'placements', 'competition', 'others']:
        mails = mails_qs.filter(direction='INBOUND', category=selected_cat)
    else:
        selected_cat = 'all'
        mails = mails_qs.filter(direction='INBOUND')

    mails.filter(is_read=False).update(is_read=True)

    counts = {
        'all': mails_qs.filter(direction='INBOUND').count(),
        'staff': mails_qs.filter(direction='INBOUND', category='staff').count(),
        'notice': mails_qs.filter(direction='INBOUND', category='notice').count(),
        'placements': mails_qs.filter(direction='INBOUND', category='placements').count(),
        'competition': mails_qs.filter(direction='INBOUND', category='competition').count(),
        'others': mails_qs.filter(direction='INBOUND', category='others').count(),
        'sent': mails_qs.filter(direction='OUTBOUND').count(),
    }

    ctx.update({
        'mails': mails,
        'selected_cat': selected_cat,
        'counts': counts,
        'subjects': Subject.objects.all().select_related('tutor'),
        'tutors': Tutor.objects.all(),
    })
    return render(request, 'students/mail_hub.html', ctx)


@login_required
@require_POST
def ai_draft_mail_api(request):
    profile = _get_student_profile(request.user)
    data = json.loads(request.body.decode('utf-8'))
    subject_id = data.get('subject_id')
    intent = data.get('intent', 'leave')
    notes = data.get('notes', '')

    subject_obj = Subject.objects.filter(id=subject_id).select_related('tutor').first() if subject_id else None
    draft = draft_tutor_email(profile, subject_obj, intent, notes)
    tutor_email = subject_obj.tutor.email if (subject_obj and subject_obj.tutor) else ""
    return JsonResponse({
        'recipient_email': tutor_email,
        'subject_line': draft['subject_line'],
        'email_body': draft['email_body'],
    })


@login_required
@require_POST
def simulate_inbound_mail(request):
    profile = _get_student_profile(request.user)
    sender = request.POST.get('sim_sender', 'Placement Cell <placements@college.edu>')
    subject = request.POST.get('sim_subject', 'TCS & Zoho Off-Campus Drive Registration')
    body = request.POST.get('sim_body', 'Submit your updated resume before Friday 5 PM for final round screening.')

    ai_meta = classify_student_mail(sender, subject, body)
    sender_name = sender.split('<')[0].strip() or sender
    sender_addr = sender.split('<')[-1].replace('>', '').strip() if '<' in sender else sender

    StudentMail.objects.create(
        student=profile,
        direction='INBOUND',
        sender_name=sender_name,
        sender_email=sender_addr,
        recipient_email=profile.college_email,
        subject=subject,
        body=body,
        category=ai_meta['category'],
        ai_summary=ai_meta['ai_summary'],
        extracted_deadline=ai_meta.get('extracted_deadline', ''),
        is_urgent=ai_meta.get('is_urgent', False),
    )
    messages.success(request, f"AI Agent sorted incoming mail into [{ai_meta['category'].upper()}]!")
    return redirect(f"/mail/?cat={ai_meta['category']}")


# 7. FEES PAYMENT & RECEIPT DOWNLOAD
@login_required
def fees_view(request):
    ctx = _base_context(request, 'fees')
    profile = ctx['profile']
    ctx['fee_records'] = FeeRecord.objects.filter(student=profile).order_by('-semester', 'due_date')
    return render(request, 'students/fees.html', ctx)


@login_required
@require_POST
def pay_fee_view(request, fee_id):
    profile = _get_student_profile(request.user)
    fee = get_object_or_404(FeeRecord, id=fee_id, student=profile)
    if fee.status != 'PAID':
        fee.mark_paid()
        messages.success(request, f"Payment confirmed! Receipt {fee.receipt_number} generated.")
    return redirect('fees')


@login_required
def download_fee_receipt(request, fee_id):
    profile = _get_student_profile(request.user)
    fee = get_object_or_404(FeeRecord, id=fee_id, student=profile, status='PAID')
    student_name = profile.user.get_full_name() or profile.user.username

    receipt_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Receipt {fee.receipt_number}</title>
<style>
  body {{ font-family: 'Courier New', monospace; background: #fff; color: #000; padding: 40px; max-width: 720px; margin: auto; }}
  .box {{ border: 2px solid #000; padding: 30px; }}
  .header {{ display: flex; justify-content: space-between; border-bottom: 2px dashed #000; padding-bottom: 16px; }}
  .badge {{ background: #D71921; color: #fff; padding: 4px 10px; font-weight: bold; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
  td, th {{ border: 1px solid #000; padding: 10px; text-align: left; }}
  .footer {{ margin-top: 30px; font-size: 12px; color: #444; }}
</style>
</head>
<body onload="window.print()">
  <div class="box">
    <div class="header">
      <div>
        <h2 style="margin:0;">NOTHING OS // ACADEMIC ERP</h2>
        <p style="margin:4px 0 0;">OFFICIAL FEE PAYMENT RECEIPT</p>
      </div>
      <div><span class="badge">PAID</span></div>
    </div>
    <table>
      <tr><th>Receipt No</th><td>{fee.receipt_number}</td></tr>
      <tr><th>Transaction ID</th><td>{fee.transaction_id}</td></tr>
      <tr><th>Student Name</th><td>{student_name}</td></tr>
      <tr><th>Roll / Register No</th><td>{profile.roll_no} / {profile.register_no}</td></tr>
      <tr><th>Department & Sem</th><td>{profile.department} — Semester {fee.semester}</td></tr>
      <tr><th>Fee Description</th><td>{fee.fee_type}</td></tr>
      <tr><th>Amount Paid</th><td><strong>INR {fee.amount}</strong></td></tr>
      <tr><th>Paid Timestamp</th><td>{fee.paid_on.strftime('%d %b %Y, %I:%M %p')}</td></tr>
    </table>
    <div class="footer">
      Generated electronically by Nothing OS Student Management System. Valid without physical signature.
    </div>
  </div>
</body>
</html>"""
    response = HttpResponse(receipt_html, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="{fee.receipt_number}.html"'
    return response


# 8. LINE AI STUDY AGENT & NOTHING ESSENTIAL KEY
@login_required
def line_agent_view(request):
    ctx = _base_context(request, 'line')
    profile = ctx['profile']

    if request.method == 'POST':
        user_msg = request.POST.get('message', '').strip()
        if user_msg:
            LineChatMessage.objects.create(student=profile, user=request.user, role='user', content=user_msg)

            att = AttendanceRecord.objects.filter(student=profile).select_related('subject')
            att_summary = ", ".join([f"{a.subject.code}: {a.percentage}%" for a in att]) or "No attendance records"
            hw_count = HomeworkSubmission.objects.filter(student=profile, status='PENDING').count()
            context_str = f"Student {profile.roll_no}, CGPA {profile.cgpa}, Attendance [{att_summary}], Pending Homeworks: {hw_count}"

            ai_res = run_line_study_agent(profile, user_msg, context_str)

            created_widget = None
            if ai_res.get('should_create_widget') and ai_res.get('widget_items'):
                created_widget = DynamicDashboardWidget.objects.create(
                    student=profile,
                    title=ai_res.get('widget_title') or "LINE STUDY WIDGET",
                    widget_type=ai_res.get('widget_type') or "STUDY_PLAN",
                    accent_red=bool(ai_res.get('accent_red', False)),
                    payload={'items': ai_res['widget_items']},
                    is_pinned=True,
                )

            LineChatMessage.objects.create(
                student=profile,
                user=request.user,
                role='assistant',
                content=ai_res['reply'],
                created_widget=created_widget,
            )
        return redirect('line_agent')

    ctx['chat_history'] = LineChatMessage.objects.filter(student=profile).select_related('created_widget').order_by('timestamp')
    ctx['widgets'] = DynamicDashboardWidget.objects.filter(student=profile).order_by('-created_at')
    return render(request, 'students/line_agent.html', ctx)


@login_required
@require_POST
def essential_key_capture(request):
    raw_input = request.POST.get('raw_input', '').strip()
    if raw_input:
        structured = process_essential_key_capture(raw_input)
        tutor = Tutor.objects.filter(user=request.user).first()
        profile = None if tutor else _get_student_profile(request.user)
        EssentialNote.objects.create(
            student=profile,
            user=request.user,
            raw_input=raw_input,
            ai_structured_action=structured['ai_structured_action'],
            tag=structured['tag'],
        )
        messages.success(request, f"Essential Key Captured [{structured['tag']}]: {structured['ai_structured_action']}")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


# 9. GOOGLE MEET INTEGRATION
@login_required
def google_meet_view(request):
    ctx = _base_context(request, 'meet')
    ctx['sessions'] = GoogleMeetSession.objects.all().select_related('subject__tutor').order_by('-is_live', 'scheduled_time')
    return render(request, 'students/google_meet.html', ctx)


# 10. LIBRARY REQUESTING CHATBOX (STUDENT <-> TUTORS)
@login_required
def library_chat_view(request):
    ctx = _base_context(request, 'library')
    profile = ctx['profile']
    student_name = profile.user.get_full_name() or profile.user.username

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'new_thread':
            tutor_id = request.POST.get('tutor_id')
            book_title = request.POST.get('book_title', '').strip()
            first_msg = request.POST.get('message', '').strip()
            tutor = get_object_or_404(Tutor, id=tutor_id)
            if book_title and first_msg:
                thread = LibraryRequestThread.objects.create(
                    student=profile,
                    tutor=tutor,
                    book_or_resource_title=book_title,
                )
                LibraryChatMessage.objects.create(
                    thread=thread,
                    sender_is_student=True,
                    sender_name=student_name,
                    message=first_msg,
                )
                messages.success(request, f"Library request thread opened with {tutor.name}.")
                return redirect(f"/library/?thread={thread.id}")

        elif action == 'send_message':
            thread_id = request.POST.get('thread_id')
            msg_text = request.POST.get('message', '').strip()
            thread = get_object_or_404(LibraryRequestThread, id=thread_id, student=profile)
            if msg_text:
                LibraryChatMessage.objects.create(
                    thread=thread,
                    sender_is_student=True,
                    sender_name=student_name,
                    message=msg_text,
                )
                thread.save()
            return redirect(f"/library/?thread={thread.id}")

    threads = LibraryRequestThread.objects.filter(student=profile).select_related('tutor').order_by('-updated_at')
    active_thread_id = request.GET.get('thread')
    active_thread = threads.filter(id=active_thread_id).first() if active_thread_id else threads.first()

    ctx.update({
        'threads': threads,
        'active_thread': active_thread,
        'tutors': Tutor.objects.filter(is_hod=False),
    })
    return render(request, 'students/library_chat.html', ctx)


# 11. NOTICE BOARD
@login_required
def notice_board_view(request):
    ctx = _base_context(request, 'notices')
    ctx['notices'] = Notice.objects.all()
    return render(request, 'students/notices.html', ctx)


# 12. STUDENT SETTINGS
@login_required
def student_settings_view(request):
    ctx = _base_context(request, 'settings')
    profile = ctx['profile']
    if request.method == 'POST':
        profile.theme_mode = request.POST.get('theme_mode', 'DARK')
        profile.glyph_alerts_enabled = request.POST.get('glyph_alerts_enabled') == 'on'
        profile.auto_triage_mail = request.POST.get('auto_triage_mail') == 'on'
        new_smtp_pass = request.POST.get('smtp_app_password', '').strip()
        if new_smtp_pass:
            profile.smtp_app_password = new_smtp_pass
        profile.save()
        messages.success(request, "Nothing OS preferences saved.")
        return redirect('settings')
    return render(request, 'students/settings.html', ctx)


def toggle_theme_view(request):
    current = request.session.get('nothing_theme', 'DARK')
    if request.user.is_authenticated:
        tutor = Tutor.objects.filter(user=request.user).first()
        if tutor:
            new_mode = 'LIGHT' if tutor.theme_mode == 'DARK' else 'DARK'
            tutor.theme_mode = new_mode
            tutor.save(update_fields=['theme_mode'])
            request.session['nothing_theme'] = new_mode
        else:
            profile = _get_student_profile(request.user)
            new_mode = 'LIGHT' if profile.theme_mode == 'DARK' else 'DARK'
            profile.theme_mode = new_mode
            profile.save(update_fields=['theme_mode'])
            request.session['nothing_theme'] = new_mode
    else:
        request.session['nothing_theme'] = 'LIGHT' if current == 'DARK' else 'DARK'
    return redirect(request.META.get('HTTP_REFERER', '/'))
