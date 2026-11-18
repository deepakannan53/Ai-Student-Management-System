import csv
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from students.models import (
    StudentProfile, Tutor, Subject, AttendanceRecord, InternalMark,
    OnlineQuiz, QuizQuestion, QuizAttempt, Homework, HomeworkSubmission,
    GoogleMeetSession, LibraryRequestThread, LibraryChatMessage, Notice,
    EssentialNote, LineChatMessage
)
from students.ai_agents import run_line_study_agent, get_ai_engine_status


def _require_tutor(user, must_be_hod=False):
    tutor = Tutor.objects.filter(user=user).first()
    if not tutor:
        return None
    if must_be_hod and not tutor.is_hod:
        return None
    return tutor


def _faculty_base_context(request, tutor, active_nav):
    essential_notes = EssentialNote.objects.filter(user=request.user).order_by('-created_at')[:6]
    open_lib = LibraryRequestThread.objects.filter(tutor=tutor, status='OPEN').count() if not tutor.is_hod else 0
    return {
        'tutor': tutor,
        'active_nav': active_nav,
        'essential_notes': essential_notes,
        'open_lib_count': open_lib,
        'glyph_active': open_lib > 0 or tutor.is_hod,
        'ai_status': get_ai_engine_status(),
    }


# ==================== 5 STAFF TUTORS PORTAL ====================
@login_required
def staff_dashboard_view(request):
    tutor = _require_tutor(request.user)
    if not tutor:
        return redirect('dashboard')
    if tutor.is_hod:
        return redirect('hod_dashboard')

    ctx = _faculty_base_context(request, tutor, 'staff_home')
    subjects = Subject.objects.filter(tutor=tutor)
    students = StudentProfile.objects.all().select_related('user')

    homeworks = Homework.objects.filter(subject__in=subjects).select_related('subject').order_by('-assigned_date')
    submissions = HomeworkSubmission.objects.filter(homework__subject__in=subjects).select_related('homework__subject', 'student__user').order_by('-submitted_at')
    quizzes = OnlineQuiz.objects.filter(subject__in=subjects).select_related('subject')
    attendance_records = AttendanceRecord.objects.filter(subject__in=subjects).select_related('student__user', 'subject')
    marks_records = InternalMark.objects.filter(subject__in=subjects).select_related('student__user', 'subject')
    meetings = GoogleMeetSession.objects.filter(subject__in=subjects).select_related('subject').order_by('-scheduled_time')
    lib_threads = LibraryRequestThread.objects.filter(tutor=tutor).select_related('student__user').order_by('-updated_at')
    line_chats = LineChatMessage.objects.filter(user=request.user).order_by('timestamp')

    ctx.update({
        'subjects': subjects,
        'students': students,
        'homeworks': homeworks,
        'submissions': submissions,
        'quizzes': quizzes,
        'attendance_records': attendance_records,
        'marks_records': marks_records,
        'meetings': meetings,
        'lib_threads': lib_threads,
        'line_chats': line_chats,
    })
    return render(request, 'staff_hod/staff_dashboard.html', ctx)


@login_required
@require_POST
def staff_assign_homework(request):
    tutor = _require_tutor(request.user)
    if not tutor:
        return redirect('dashboard')

    subject = get_object_or_404(Subject, id=request.POST.get('subject_id'), tutor=tutor)
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    due_days = int(request.POST.get('due_days', 3) or 3)

    if title and description:
        hw = Homework.objects.create(
            subject=subject,
            title=title,
            description=description,
            due_date=timezone.now() + timedelta(days=due_days),
        )
        for st in StudentProfile.objects.all():
            HomeworkSubmission.objects.get_or_create(homework=hw, student=st)
        messages.success(request, f"Homework '{title}' assigned to students under {subject.code}.")
    return redirect('staff_dashboard')


@login_required
@require_POST
def staff_grade_homework(request, sub_id):
    tutor = _require_tutor(request.user)
    if not tutor:
        return redirect('dashboard')
    sub = get_object_or_404(HomeworkSubmission, id=sub_id, homework__subject__tutor=tutor)
    sub.status = 'GRADED'
    sub.remarks = request.POST.get('remarks', 'Evaluated & Approved')[:255]
    sub.save()
    messages.success(request, f"Graded {sub.student.roll_no}'s submission for {sub.homework.title}.")
    return redirect('staff_dashboard')


@login_required
@require_POST
def staff_create_quiz(request):
    tutor = _require_tutor(request.user)
    if not tutor:
        return redirect('dashboard')

    subject = get_object_or_404(Subject, id=request.POST.get('subject_id'), tutor=tutor)
    title = request.POST.get('title', '').strip()
    duration = int(request.POST.get('duration_minutes', 15) or 15)
    max_tabs = int(request.POST.get('max_tab_switches', 2) or 2)

    q_text = request.POST.get('q_text', '').strip()
    opt_a = request.POST.get('opt_a', '').strip()
    opt_b = request.POST.get('opt_b', '').strip()
    opt_c = request.POST.get('opt_c', '').strip()
    opt_d = request.POST.get('opt_d', '').strip()
    correct = request.POST.get('correct_option', 'A')

    if title and q_text:
        quiz = OnlineQuiz.objects.create(
            subject=subject,
            title=title,
            duration_minutes=duration,
            total_marks=1,
            max_tab_switches=max_tabs,
            require_fullscreen=True,
            deadline=timezone.now() + timedelta(days=5),
            is_active=True,
        )
        QuizQuestion.objects.create(
            quiz=quiz,
            question_text=q_text,
            option_a=opt_a or "Option A",
            option_b=opt_b or "Option B",
            option_c=opt_c or "Option C",
            option_d=opt_d or "Option D",
            correct_option=correct,
            marks=1,
        )
        messages.success(request, f"Proctored Quiz '{title}' published for {subject.code}.")
    return redirect('staff_dashboard')


@login_required
@require_POST
def staff_update_attendance(request):
    tutor = _require_tutor(request.user)
    if not tutor:
        return redirect('dashboard')
    rec = get_object_or_404(AttendanceRecord, id=request.POST.get('record_id'), subject__tutor=tutor)
    rec.attended_classes = int(request.POST.get('attended_classes', rec.attended_classes))
    rec.total_classes = int(request.POST.get('total_classes', rec.total_classes))
    rec.save()
    messages.success(request, f"Updated attendance for {rec.student.roll_no} in {rec.subject.code} ({rec.percentage}%).")
    return redirect('staff_dashboard')


@login_required
@require_POST
def staff_update_marks(request):
    tutor = _require_tutor(request.user)
    if not tutor:
        return redirect('dashboard')
    mark = get_object_or_404(InternalMark, id=request.POST.get('mark_id'), subject__tutor=tutor)
    mark.cia_1 = float(request.POST.get('cia_1', mark.cia_1))
    mark.cia_2 = float(request.POST.get('cia_2', mark.cia_2))
    mark.model_exam = float(request.POST.get('model_exam', mark.model_exam))
    mark.assignment_marks = float(request.POST.get('assignment_marks', mark.assignment_marks))
    mark.save()
    messages.success(request, f"Updated internal marks for {mark.student.roll_no} in {mark.subject.code}.")
    return redirect('staff_dashboard')


@login_required
@require_POST
def staff_schedule_meet(request):
    tutor = _require_tutor(request.user)
    if not tutor:
        return redirect('dashboard')
    subject = get_object_or_404(Subject, id=request.POST.get('subject_id'), tutor=tutor)
    topic = request.POST.get('topic', '').strip()
    meet_url = request.POST.get('meet_url', 'https://meet.google.com/new').strip()
    if topic:
        GoogleMeetSession.objects.create(
            subject=subject,
            topic=topic,
            meet_url=meet_url,
            scheduled_time=timezone.now(),
            duration_minutes=60,
            is_live=True,
        )
        messages.success(request, f"Live Google Meet session '{topic}' pushed to student dashboards.")
    return redirect('staff_dashboard')


@login_required
@require_POST
def staff_library_reply(request, thread_id):
    tutor = _require_tutor(request.user)
    if not tutor:
        return redirect('dashboard')
    thread = get_object_or_404(LibraryRequestThread, id=thread_id, tutor=tutor)
    reply_msg = request.POST.get('message', '').strip()
    new_status = request.POST.get('status', thread.status)
    if reply_msg:
        LibraryChatMessage.objects.create(
            thread=thread,
            sender_is_student=False,
            sender_name=tutor.name,
            message=reply_msg,
        )
    thread.status = new_status
    thread.save()
    messages.success(request, f"Replied to {thread.student.roll_no}'s library request ({thread.status}).")
    return redirect('staff_dashboard')


@login_required
@require_POST
def faculty_line_chat_view(request):
    tutor = _require_tutor(request.user)
    if not tutor:
        return redirect('dashboard')
    user_msg = request.POST.get('message', '').strip()
    if user_msg:
        LineChatMessage.objects.create(user=request.user, role='user', content=user_msg)
        role_label = f"HOD {tutor.name}" if tutor.is_hod else f"Faculty {tutor.name}"
        context_str = f"{role_label}, Dept: {tutor.department}, Total Students: {StudentProfile.objects.count()}, Active Notices: {Notice.objects.count()}"
        ai_res = run_line_study_agent(None, user_msg, context_str)
        LineChatMessage.objects.create(user=request.user, role='assistant', content=ai_res['reply'])
    return redirect('hod_dashboard' if tutor.is_hod else 'staff_dashboard')


# ==================== 1 HOD PORTAL ====================
@login_required
def hod_dashboard_view(request):
    hod = _require_tutor(request.user, must_be_hod=True)
    if not hod:
        return redirect('dashboard')

    ctx = _faculty_base_context(request, hod, 'hod_home')
    tutors = Tutor.objects.filter(is_hod=False).prefetch_related('subjects')
    tutor_cards = []
    for t in tutors:
        subjs = list(t.subjects.all())
        hw_count = Homework.objects.filter(subject__in=subjs).count()
        quiz_count = OnlineQuiz.objects.filter(subject__in=subjs).count()
        att_qs = AttendanceRecord.objects.filter(subject__in=subjs)
        avg_att = round(sum(a.percentage for a in att_qs) / len(att_qs), 1) if att_qs else 100.0
        lib_open = LibraryRequestThread.objects.filter(tutor=t, status='OPEN').count()
        tutor_cards.append({
            'tutor': t,
            'subjects': subjs,
            'hw_count': hw_count,
            'quiz_count': quiz_count,
            'avg_att': avg_att,
            'lib_open': lib_open,
        })

    students = StudentProfile.objects.all().select_related('user')
    notices = Notice.objects.all()
    line_chats = LineChatMessage.objects.filter(user=request.user).order_by('timestamp')

    ctx.update({
        'tutor_cards': tutor_cards,
        'students': students,
        'notices': notices,
        'total_homeworks': Homework.objects.count(),
        'total_quizzes': OnlineQuiz.objects.count(),
        'line_chats': line_chats,
    })
    return render(request, 'staff_hod/hod_dashboard.html', ctx)


@login_required
@require_POST
def hod_post_notice(request):
    hod = _require_tutor(request.user, must_be_hod=True)
    if not hod:
        return redirect('dashboard')

    title = request.POST.get('title', '').strip()
    content = request.POST.get('content', '').strip()
    priority = request.POST.get('priority', 'NORMAL')
    if title and content:
        Notice.objects.create(
            title=title,
            content=content,
            posted_by=f"{hod.name} (HOD - {hod.department})",
            priority=priority,
        )
        messages.success(request, f"Official HOD Notice '{title}' published to all students & staff.")
    return redirect('hod_dashboard')


@login_required
@require_POST
def hod_delete_notice(request, notice_id):
    hod = _require_tutor(request.user, must_be_hod=True)
    if not hod:
        return redirect('dashboard')
    notice = get_object_or_404(Notice, id=notice_id)
    notice.delete()
    messages.info(request, "Notice removed from Notice Board.")
    return redirect('hod_dashboard')


@login_required
def hod_tutor_detail_view(request, tutor_id):
    hod = _require_tutor(request.user, must_be_hod=True)
    if not hod:
        return redirect('dashboard')

    ctx = _faculty_base_context(request, hod, 'hod_home')
    target_tutor = get_object_or_404(Tutor, id=tutor_id, is_hod=False)
    subjects = Subject.objects.filter(tutor=target_tutor)
    ctx.update({
        'target_tutor': target_tutor,
        'subjects': subjects,
        'homeworks': Homework.objects.filter(subject__in=subjects).select_related('subject'),
        'quizzes': OnlineQuiz.objects.filter(subject__in=subjects).select_related('subject'),
        'attendance_records': AttendanceRecord.objects.filter(subject__in=subjects).select_related('student__user', 'subject'),
        'marks_records': InternalMark.objects.filter(subject__in=subjects).select_related('student__user', 'subject'),
        'library_threads': LibraryRequestThread.objects.filter(tutor=target_tutor).select_related('student__user'),
    })
    return render(request, 'staff_hod/hod_tutor_detail.html', ctx)


@login_required
def hod_download_report(request, report_type):
    hod = _require_tutor(request.user, must_be_hod=True)
    if not hod:
        return redirect('dashboard')

    response = HttpResponse(content_type='text/csv')
    writer = csv.writer(response)

    if report_type == 'tutors':
        response['Content-Disposition'] = 'attachment; filename="HOD_Tutors_Performance_Report.csv"'
        writer.writerow(['Staff Code', 'Tutor Name', 'Designation', 'Email', 'Assigned Subjects', 'Homeworks Assigned', 'Quizzes Created', 'Avg Class Attendance %'])
        for t in Tutor.objects.filter(is_hod=False):
            subjs = list(t.subjects.all())
            subj_codes = ", ".join(s.code for s in subjs)
            hw_c = Homework.objects.filter(subject__in=subjs).count()
            qz_c = OnlineQuiz.objects.filter(subject__in=subjs).count()
            att_qs = AttendanceRecord.objects.filter(subject__in=subjs)
            avg_att = round(sum(a.percentage for a in att_qs) / len(att_qs), 1) if att_qs else 100.0
            writer.writerow([t.staff_code, t.name, t.designation, t.email, subj_codes, hw_c, qz_c, avg_att])

    elif report_type == 'academics':
        response['Content-Disposition'] = 'attachment; filename="HOD_Student_Attendance_Marks_Report.csv"'
        writer.writerow(['Roll No', 'Student Name', 'Subject Code', 'Subject Name', 'Tutor', 'Attended', 'Total Classes', 'Attendance %', 'CIA-1', 'CIA-2', 'Model', 'Assignment', 'Total Internal'])
        for att in AttendanceRecord.objects.select_related('student__user', 'subject__tutor'):
            mark = InternalMark.objects.filter(student=att.student, subject=att.subject).first()
            writer.writerow([
                att.student.roll_no,
                att.student.user.get_full_name() or att.student.user.username,
                att.subject.code,
                att.subject.name,
                att.subject.tutor.name if att.subject.tutor else '',
                att.attended_classes,
                att.total_classes,
                att.percentage,
                mark.cia_1 if mark else 0,
                mark.cia_2 if mark else 0,
                mark.model_exam if mark else 0,
                mark.assignment_marks if mark else 0,
                mark.total_internal if mark else 0,
            ])

    else:  # master department report
        response['Content-Disposition'] = 'attachment; filename="HOD_Department_Master_Report.csv"'
        writer.writerow(['Roll No', 'Register No', 'Student Name', 'Department', 'Semester', 'CGPA', 'Homework Completed', 'Quizzes Attempted'])
        for st in StudentProfile.objects.select_related('user'):
            hw_done = HomeworkSubmission.objects.filter(student=st).exclude(status='PENDING').count()
            qz_done = QuizAttempt.objects.filter(student=st, is_completed=True).count()
            writer.writerow([
                st.roll_no, st.register_no,
                st.user.get_full_name() or st.user.username,
                st.department, st.semester, st.cgpa, hw_done, qz_done
            ])

    return response
