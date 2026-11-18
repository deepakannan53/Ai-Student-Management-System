from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from students.models import (
    StudentProfile, Tutor, Subject, AttendanceRecord, InternalMark,
    OnlineQuiz, QuizQuestion, Homework, HomeworkSubmission,
    StudentMail, FeeRecord, DynamicDashboardWidget,
    LineChatMessage, GoogleMeetSession, LibraryRequestThread, LibraryChatMessage, Notice
)


class Command(BaseCommand):
    help = "Seeds 1 Student, 5 Staff Tutors, 1 HOD, Subjects, Quizzes, Homework & LINE AI widgets"

    def handle(self, *args, **options):
        # 1. Seed Student Account
        st_user, created = User.objects.get_or_create(
            username="student",
            defaults={
                "first_name": "Deepa",
                "last_name": "Kannan",
                "email": "deepa.mca26@college.edu",
            }
        )
        if created:
            st_user.set_password("nothing123")
            st_user.save()

        profile, _ = StudentProfile.objects.get_or_create(
            user=st_user,
            defaults={
                "roll_no": "26MCA042",
                "register_no": "312426205042",
                "department": "Master of Computer Applications (MCA)",
                "semester": 1,
                "section": "A",
                "phone": "+91 98401 22410",
                "cgpa": 8.92,
                "avatar_initials": "DK",
                "college_email": "deepa.mca26@college.edu",
            }
        )

        # 2. Seed 1 HOD Account (username: hod / nothing123)
        hod_user, h_created = User.objects.get_or_create(
            username="hod",
            defaults={
                "first_name": "Dr. S.",
                "last_name": "Natarajan",
                "email": "hod.mca@college.edu",
            }
        )
        if h_created:
            hod_user.set_password("nothing123")
            hod_user.save()

        Tutor.objects.get_or_create(
            email="hod.mca@college.edu",
            defaults={
                "user": hod_user,
                "staff_code": "HOD001",
                "name": "Dr. S. Natarajan",
                "department": "Master of Computer Applications (MCA)",
                "designation": "Professor & Head of Department",
                "is_hod": True,
            }
        )

        # 3. Seed 5 Staff Tutors (staff1 .. staff5 / nothing123) + 5 Subjects
        staff_specs = [
            ("staff1", "Dr. R.", "Aravind", "Dr. R. Aravind", "aravind.cs@college.edu", "STF101", "Professor", "MCA101", "Advanced Data Structures & Algorithms", 4),
            ("staff2", "Prof. S.", "Meera", "Prof. S. Meera", "meera.ai@college.edu", "STF102", "Associate Professor", "MCA102", "Agentic AI & Machine Learning", 4),
            ("staff3", "Prof. K.", "Karthik", "Prof. K. Karthik", "karthik.db@college.edu", "STF103", "Assistant Professor", "MCA103", "Distributed Database Systems", 3),
            ("staff4", "Dr. V.", "Priya", "Dr. V. Priya", "priya.cloud@college.edu", "STF104", "Associate Professor", "MCA104", "Cloud Native & Docker Architecture", 4),
            ("staff5", "Prof. M.", "Anand", "Prof. M. Anand", "anand.sec@college.edu", "STF105", "Assistant Professor", "MCA105", "Cybersecurity & Cryptography", 3),
        ]

        created_subjects = []
        created_tutors = []
        for uname, fname, lname, full_name, mail_addr, scode, desig, subj_code, subj_name, creds in staff_specs:
            u, u_created = User.objects.get_or_create(
                username=uname,
                defaults={"first_name": fname, "last_name": lname, "email": mail_addr}
            )
            if u_created:
                u.set_password("nothing123")
                u.save()

            tutor, _ = Tutor.objects.get_or_create(
                email=mail_addr,
                defaults={
                    "user": u,
                    "staff_code": scode,
                    "name": full_name,
                    "department": "Master of Computer Applications (MCA)",
                    "designation": desig,
                    "is_hod": False,
                }
            )
            if not tutor.user:
                tutor.user = u
                tutor.save()

            subj, _ = Subject.objects.get_or_create(
                code=subj_code,
                defaults={"name": subj_name, "semester": 1, "credits": creds, "tutor": tutor}
            )
            created_tutors.append(tutor)
            created_subjects.append(subj)

        s1, s2, s3, s4, s5 = created_subjects
        t1, t2, t3, t4, t5 = created_tutors

        # Attendance & Internal Marks across all 5 subjects
        att_data = [
            (s1, 32, 29),
            (s2, 30, 26),
            (s3, 28, 19),  # 67.9% -> triggers Red Glyph Alert
            (s4, 26, 23),
            (s5, 24, 21),
        ]
        for subj, tot, att in att_data:
            AttendanceRecord.objects.get_or_create(student=profile, subject=subj, defaults={"total_classes": tot, "attended_classes": att})

        marks_data = [
            (s1, 18.5, 19.0, 44.0, 9.5),
            (s2, 19.0, 18.0, 46.0, 10.0),
            (s3, 15.0, 16.5, 38.0, 8.0),
            (s4, 17.5, 18.5, 42.0, 9.0),
            (s5, 18.0, 17.5, 43.0, 9.0),
        ]
        for subj, c1, c2, mod, asg in marks_data:
            InternalMark.objects.get_or_create(
                student=profile, subject=subj,
                defaults={"cia_1": c1, "cia_2": c2, "model_exam": mod, "assignment_marks": asg}
            )

        # Online Quiz assigned by Staff 2
        quiz, q_created = OnlineQuiz.objects.get_or_create(
            subject=s2,
            title="CIA-1 Online Assessment: LLM Agents & RAG",
            defaults={
                "duration_minutes": 15,
                "total_marks": 3,
                "max_tab_switches": 2,
                "require_fullscreen": True,
                "deadline": timezone.now() + timedelta(days=3),
            }
        )
        if q_created:
            QuizQuestion.objects.create(
                quiz=quiz,
                question_text="Which SQLite pragma prevents database locks during concurrent background AI writes?",
                option_a="PRAGMA journal_mode=WAL;",
                option_b="PRAGMA cache_size=0;",
                option_c="PRAGMA locking_mode=EXCLUSIVE;",
                option_d="PRAGMA temp_store=MEMORY;",
                correct_option="A",
                marks=1,
            )
            QuizQuestion.objects.create(
                quiz=quiz,
                question_text="In an agentic workflow, what enables an LLM to safely invoke backend Django ORM functions?",
                option_a="Raw SQL string interpolation",
                option_b="Structured JSON Schema Tool-Calling",
                option_c="CSS Grid Layouts",
                option_d="IMAP IDLE polling",
                correct_option="B",
                marks=1,
            )
            QuizQuestion.objects.create(
                quiz=quiz,
                question_text="Which protocol is used by the student module to dispatch outbound emails to faculty tutors?",
                option_a="FTP",
                option_b="SNMP",
                option_c="SMTP",
                option_d="WebRTC",
                correct_option="C",
                marks=1,
            )

        # Homeworks assigned by the 5 Staff members
        hw_specs = [
            (s1, "Implement Red-Black Tree Insertion & Balancing", "Submit Python/C++ code with O(log n) rotation proofs.", 2),
            (s2, "Build a Pydantic Structured Output Agent", "Create a tool-calling agent with fallback handling.", 3),
            (s3, "Two-Phase Commit Protocol Case Study", "Analyze coordinator failure recovery in distributed SQLite clusters.", 4),
            (s4, "Multi-Stage Dockerfile Optimization Lab", "Containerize a Django app under 120MB image footprint.", 5),
            (s5, "RSA & Elliptic Curve Key Exchange Benchmark", "Compare handshake latency and key strength metrics.", 6),
        ]
        for subj, h_title, h_desc, d_days in hw_specs:
            hw, _ = Homework.objects.get_or_create(
                subject=subj,
                title=h_title,
                defaults={"description": h_desc, "due_date": timezone.now() + timedelta(days=d_days)}
            )
            HomeworkSubmission.objects.get_or_create(homework=hw, student=profile)

        # AI-Sorted Mails
        if not StudentMail.objects.filter(student=profile).exists():
            sample_mails = [
                ("Dr. R. Aravind", "aravind.cs@college.edu", "MCA101 Lab Evaluation Rubrics",
                 "Dear Students, please bring your completed Red-Black tree implementation to Friday's lab session.",
                 "staff", "Lab evaluation rubrics shared for MCA101; bring Red-Black tree code.", "Friday 2:00 PM", False),
                ("Placement Cell", "placements@college.edu", "Zoho & Juspay Software Engineer Drive 2026",
                 "Eligible MCA students with CGPA > 8.0 must register before tomorrow 6 PM for online aptitude.",
                 "placements", "Zoho & Juspay campus hiring open for >8.0 CGPA students.", "Tomorrow 6:00 PM", True),
                ("DEXATHON Organizing Team", "hackathon@sathyabama.ac.in", "24-Hour National AI Hackathon Shortlist",
                 "Team Spectaculars is invited to the grand finale pitch round. Confirm hardware requirements.",
                 "competition", "Finalist confirmation for 24-hour National AI Hackathon.", "Next Monday", True),
                ("Dr. S. Natarajan (HOD)", "hod.mca@college.edu", "Semester I End-Semester Exam & Attendance Circular",
                 "All students must maintain >=75% attendance across MCA101-MCA105 before end-semester hall ticket generation.",
                 "notice", "HOD circular enforcing 75% attendance cutoff across all 5 subjects.", "Dec 14, 2026", True),
                ("GitHub Student Developer Pack", "education@github.com", "Your Student Pack Benefits Renewed",
                 "Enjoy free cloud credits, Copilot Pro, and domain perks for your academic projects.",
                 "others", "GitHub Student Developer Pack benefits renewed for 2026.", "", False),
            ]
            for s_name, s_mail, subj, body, cat, summary, dl, urg in sample_mails:
                StudentMail.objects.create(
                    student=profile,
                    direction='INBOUND',
                    sender_name=s_name,
                    sender_email=s_mail,
                    recipient_email=profile.college_email,
                    subject=subj,
                    body=body,
                    category=cat,
                    ai_summary=summary,
                    extracted_deadline=dl,
                    is_urgent=urg,
                )

        # Fees
        FeeRecord.objects.get_or_create(
            student=profile, semester=1, fee_type="Semester I Tuition & AI Lab Fee",
            defaults={"amount": 42500.00, "due_date": (timezone.now() + timedelta(days=10)).date(), "status": "PENDING"}
        )
        paid_fee, p_created = FeeRecord.objects.get_or_create(
            student=profile, semester=1, fee_type="Admission & University Registration Fee",
            defaults={"amount": 8500.00, "due_date": (timezone.now() - timedelta(days=30)).date()}
        )
        if p_created:
            paid_fee.mark_paid()

        # LINE AI Dynamic Dashboard Widget
        if not DynamicDashboardWidget.objects.filter(student=profile).exists():
            w = DynamicDashboardWidget.objects.create(
                student=profile,
                title="MCA103 ATTENDANCE RECOVERY + EXAM SPRINT",
                widget_type="STUDY_PLAN",
                accent_red=True,
                payload={
                    "items": [
                        "Attend next 4 consecutive MCA103 classes (Prof. Karthik) to cross 75%",
                        "Complete MCA101 Red-Black Tree & MCA104 Docker homework",
                        "Attempt MCA102 LLM Agents Online Quiz in fullscreen mode",
                    ]
                },
                is_pinned=True,
            )
            LineChatMessage.objects.create(
                student=profile,
                user=st_user,
                role="assistant",
                content="Welcome back, Deepa. Your MCA103 attendance is at 67.9% (below 75%). I've pinned an active recovery & study sprint widget onto your Overall Dashboard.",
                created_widget=w,
            )

        # Google Meet Live Session
        GoogleMeetSession.objects.get_or_create(
            subject=s2,
            topic="Live Doubt Clearing: Multi-Agent Tool Calling & SQLite",
            defaults={
                "meet_url": "https://meet.google.com/new",
                "scheduled_time": timezone.now() + timedelta(minutes=30),
                "duration_minutes": 60,
                "is_live": True,
            }
        )

        # Library Request Thread
        thread, t_created = LibraryRequestThread.objects.get_or_create(
            student=profile,
            tutor=t2,
            book_or_resource_title="Designing Data-Intensive Applications (Martin Kleppmann)",
        )
        if t_created:
            LibraryChatMessage.objects.create(
                thread=thread,
                sender_is_student=True,
                sender_name="Deepa Kannan",
                message="Respected Madam, could you approve a 14-day department library issue for this book for my MCA103 seminar?",
            )
            LibraryChatMessage.objects.create(
                thread=thread,
                sender_is_student=False,
                sender_name="Prof. S. Meera",
                message="Approved! Collect copy #04 from the MCA Reference Counter after 3:30 PM today.",
            )

        # Notices posted by HOD
        Notice.objects.get_or_create(
            title="Mandatory 75% Attendance Cutoff for Semester I CIA-2",
            defaults={
                "content": "Students falling below 75% attendance in any of the 5 MCA courses must submit valid medical/OD documentation via the AI Mail module before Friday.",
                "posted_by": "Dr. S. Natarajan (HOD - Master of Computer Applications (MCA))",
                "priority": "URGENT",
            }
        )
        Notice.objects.get_or_create(
            title="Nothing OS Campus Innovation Challenge Registrations Open",
            defaults={
                "content": "Build minimalist, AI-first student utilities. Submit your GitHub repository link to the Department Innovation Cell.",
                "posted_by": "Dr. S. Natarajan (HOD - Master of Computer Applications (MCA))",
                "priority": "NORMAL",
            }
        )

        self.stdout.write(self.style.SUCCESS("Seeded 1 Student, 5 Staff Tutors, and 1 HOD successfully!"))
