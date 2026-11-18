import json
from django.test import TestCase, Client
from django.core.management import call_command
from django.urls import reverse
from students.models import (
    StudentMail, OnlineQuiz, QuizAttempt, FeeRecord,
    DynamicDashboardWidget, EssentialNote, HomeworkSubmission, LibraryRequestThread, Notice, Tutor
)


class NothingMultiRoleSystemTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_nothing_sms')

    def setUp(self):
        self.client = Client()

    def test_01_student_dashboard_and_essential_key(self):
        self.assertTrue(self.client.login(username='student', password='nothing123'))
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "26MCA042")

        resp_ek = self.client.post(reverse('essential_key_capture'), {
            'raw_input': 'Revise SQLite WAL mode before lab tomorrow'
        })
        self.assertEqual(resp_ek.status_code, 302)
        self.assertTrue(EssentialNote.objects.filter(tag='LAB').exists())

    def test_02_student_line_ai_dynamic_widget(self):
        self.assertTrue(self.client.login(username='student', password='nothing123'))
        before = DynamicDashboardWidget.objects.count()
        resp = self.client.post(reverse('line_agent'), {
            'message': 'Create a pinned revision widget plan for my exams'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertGreater(DynamicDashboardWidget.objects.count(), before)

    def test_03_five_staff_tutors_assign_work_and_grade(self):
        self.assertEqual(Tutor.objects.filter(is_hod=False).count(), 5)
        self.assertTrue(self.client.login(username='staff1', password='nothing123'))
        resp = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dr. R. Aravind")

        subj = Tutor.objects.get(staff_code='STF101').subjects.first()
        resp_hw = self.client.post(reverse('staff_assign_homework'), {
            'subject_id': subj.id,
            'title': 'Graph Dijkstra Lab Exercise',
            'description': 'Implement shortest path using priority queue.',
            'due_days': 4,
        })
        self.assertEqual(resp_hw.status_code, 302)
        self.assertTrue(HomeworkSubmission.objects.filter(homework__title='Graph Dijkstra Lab Exercise').exists())

    def test_04_hod_posts_notice_views_tutors_and_downloads_reports(self):
        self.assertTrue(self.client.login(username='hod', password='nothing123'))
        resp = self.client.get(reverse('hod_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dr. S. Natarajan")

        # Post Notice
        resp_notice = self.client.post(reverse('hod_post_notice'), {
            'title': 'End Semester Practical Viva Dates',
            'content': 'Viva starts Monday 9:00 AM across all labs.',
            'priority': 'URGENT',
        })
        self.assertEqual(resp_notice.status_code, 302)
        self.assertTrue(Notice.objects.filter(title='End Semester Practical Viva Dates').exists())

        # Inspect Tutor Data
        t1 = Tutor.objects.get(staff_code='STF101')
        resp_td = self.client.get(reverse('hod_tutor_detail', args=[t1.id]))
        self.assertEqual(resp_td.status_code, 200)

        # Download CSV Reports
        for r_type in ['master', 'tutors', 'academics']:
            resp_csv = self.client.get(reverse('hod_download_report', args=[r_type]))
            self.assertEqual(resp_csv.status_code, 200)
            self.assertEqual(resp_csv['Content-Type'], 'text/csv')


    def test_05_light_and_dark_theme_toggle_all_roles(self):
        # Student toggle
        self.assertTrue(self.client.login(username='student', password='nothing123'))
        self.client.get(reverse('toggle_theme'))
        resp_st = self.client.get(reverse('dashboard'))
        self.assertContains(resp_st, 'light-theme')

        # Staff toggle
        self.assertTrue(self.client.login(username='staff1', password='nothing123'))
        self.client.get(reverse('toggle_theme'))
        resp_sf = self.client.get(reverse('staff_dashboard'))
        self.assertContains(resp_sf, 'light-theme')

        # HOD toggle
        self.assertTrue(self.client.login(username='hod', password='nothing123'))
        self.client.get(reverse('toggle_theme'))
        resp_hd = self.client.get(reverse('hod_dashboard'))
        self.assertContains(resp_hd, 'light-theme')
