from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Attendance, AuditLog, Department, Employee, Holiday, LeaveRequest, OvertimeRequest, Shift


class EmployeeManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='admin', password='StrongPass123!')
        self.department = Department.objects.create(
            name='Production',
            code='PROD',
            description='Main factory area',
        )
        self.shift = Shift.objects.create(
            name='Morning',
            start_time='08:00:00',
            end_time='17:00:00',
            grace_period_minutes=10,
            working_hours=9.00,
            is_overnight=False,
            is_active=True,
        )

    def test_employee_creation(self):
        employee = Employee.objects.create(
            employee_id='EMP-1001',
            first_name='Alice',
            last_name='Brown',
            gender='Female',
            department=self.department,
            position='Operator',
            shift=self.shift,
            user=self.user,
        )
        self.assertEqual(employee.employee_id, 'EMP-1001')
        self.assertEqual(employee.department.name, 'Production')

    def test_employee_list_page_requires_login(self):
        response = self.client.get(reverse('employee_list'))
        self.assertEqual(response.status_code, 302)


class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='manager', password='StrongPass123!')
        self.department = Department.objects.create(name='Production', code='PROD')
        self.employee = Employee.objects.create(
            employee_id='EMP-2001',
            first_name='Sam',
            last_name='Taylor',
            gender='Male',
            department=self.department,
            position='Operator',
        )
        self.client.force_login(self.user)

    def test_dashboard_shows_only_pending_leave_requests_for_approval(self):
        pending_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type='Annual Leave',
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            reason='Planned time off',
            status='Pending',
        )
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type='Sick Leave',
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            reason='Already reviewed',
            status='Approved',
        )

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pending_leave_count'], 1)
        self.assertEqual(list(response.context['recent_leaves']), [pending_request])


class PayrollSummaryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='payrollmanager', password='StrongPass123!')
        self.department = Department.objects.create(name='Production', code='PROD', description='Factory floor')
        Employee.objects.create(
            employee_id='EMP-3001',
            first_name='Taylor',
            last_name='Moss',
            gender='Male',
            department=self.department,
            position='Supervisor',
            employment_status='Active',
        )
        self.client.force_login(self.user)

    def test_payroll_summary_page_loads(self):
        response = self.client.get(reverse('payroll_summary'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Payroll Summary')


class EmployeeBiometricInfoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='biometricuser', password='StrongPass123!')
        self.department = Department.objects.create(name='Security', code='SEC', description='Security staff')

    def test_employee_biometric_fields_are_stored(self):
        employee = Employee.objects.create(
            employee_id='EMP-5001',
            first_name='Nora',
            last_name='Field',
            gender='Female',
            department=self.department,
            position='Supervisor',
            biometric_id='BIO-001',
            biometric_device='Phone',
            biometric_device_type='Mobile Phone',
            mobile_device_id='ANDROID-PIXEL-9',
            biometric_status='Enrolled',
            biometric_notes='Right index enrolled',
        )

        self.assertEqual(employee.biometric_id, 'BIO-001')
        self.assertEqual(employee.biometric_device, 'Phone')
        self.assertEqual(employee.biometric_device_type, 'Mobile Phone')
        self.assertEqual(employee.mobile_device_id, 'ANDROID-PIXEL-9')
        self.assertEqual(employee.biometric_status, 'Enrolled')

    def test_employee_detail_shows_biometric_section(self):
        employee = Employee.objects.create(
            employee_id='EMP-5002',
            first_name='Omar',
            last_name='Smith',
            gender='Male',
            department=self.department,
            position='Guard',
            biometric_id='BIO-002',
            biometric_device='Phone',
            biometric_device_type='Mobile Phone',
            mobile_device_id='IPHONE-15',
            biometric_status='Pending',
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('employee_detail', args=[employee.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Biometric ID')
        self.assertContains(response, 'BIO-002')
        self.assertContains(response, 'Mobile Phone')


class DepartmentAndShiftTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='manager', password='StrongPass123!')

    def test_department_creation(self):
        department = Department.objects.create(
            name='Warehouse',
            code='WH',
            description='Goods storage',
            manager=self.user,
        )
        self.assertEqual(department.name, 'Warehouse')
        self.assertEqual(department.code, 'WH')

    def test_shift_creation(self):
        shift = Shift.objects.create(
            name='Night',
            start_time='22:00:00',
            end_time='06:00:00',
            grace_period_minutes=15,
            working_hours=8.00,
            is_overnight=True,
            is_active=True,
        )
        self.assertEqual(shift.name, 'Night')
        self.assertTrue(shift.is_overnight)


class AttendanceLogicTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='employee1', password='StrongPass123!')
        self.department = Department.objects.create(name='Production', code='PROD', description='Factory')
        self.shift = Shift.objects.create(
            name='Morning',
            start_time='08:00:00',
            end_time='17:00:00',
            grace_period_minutes=10,
            working_hours=8.00,
            is_overnight=False,
            is_active=True,
        )
        self.employee = Employee.objects.create(
            employee_id='EMP-2001',
            first_name='John',
            last_name='Smith',
            gender='Male',
            department=self.department,
            position='Technician',
            shift=self.shift,
            user=self.user,
        )

    def test_late_minutes_calculation(self):
        check_in = timezone.make_aware(datetime(2025, 1, 15, 8, 20))
        status, late_minutes = self.shift.calculate_checkin_status(check_in)
        self.assertEqual(status, 'Late')
        self.assertEqual(late_minutes, 10)

    def test_present_when_checkin_before_grace(self):
        check_in = timezone.make_aware(datetime(2025, 1, 15, 7, 55))
        status, late_minutes = self.shift.calculate_checkin_status(check_in)
        self.assertEqual(status, 'Present')
        self.assertEqual(late_minutes, 0)

    def test_overtime_calculation(self):
        check_in = timezone.make_aware(datetime(2025, 1, 15, 8, 0))
        check_out = timezone.make_aware(datetime(2025, 1, 15, 17, 30))
        total_hours, overtime = self.shift.calculate_work_duration(check_in, check_out)
        self.assertEqual(total_hours, 9.5)
        self.assertEqual(overtime, 1.5)

    def test_duplicate_attendance_prevention(self):
        Attendance.objects.create(
            employee=self.employee,
            date='2025-01-15',
            check_in=timezone.make_aware(datetime(2025, 1, 15, 8, 0)),
            status='Present',
        )
        with self.assertRaises(IntegrityError):
            Attendance.objects.create(
                employee=self.employee,
                date='2025-01-15',
                check_in=timezone.make_aware(datetime(2025, 1, 15, 8, 10)),
                status='Late',
            )

    def test_phone_biometric_check_in_requires_matching_device_id(self):
        user = get_user_model().objects.create_user(username='mobile-user-1', password='StrongPass123!')
        employee = Employee.objects.create(
            employee_id='EMP-2002',
            first_name='Sara',
            last_name='Nolan',
            gender='Female',
            department=self.department,
            position='Operator',
            shift=self.shift,
            user=user,
            biometric_device='Phone',
            biometric_device_type='Mobile Phone',
            mobile_device_id='ANDROID-PIXEL-9',
            biometric_status='Enrolled',
        )

        self.client.force_login(user)
        response = self.client.post(reverse('attendance_check_in'), {'device_id': 'ANDROID-PIXEL-9'})

        self.assertEqual(response.status_code, 302)
        record = Attendance.objects.get(employee=employee, date=timezone.localdate())
        self.assertEqual(record.verification_method, 'Mobile Phone')
        self.assertEqual(record.verification_device_id, 'ANDROID-PIXEL-9')

    def test_phone_biometric_check_in_rejects_wrong_device_id(self):
        user = get_user_model().objects.create_user(username='mobile-user-2', password='StrongPass123!')
        employee = Employee.objects.create(
            employee_id='EMP-2003',
            first_name='Liam',
            last_name='Stone',
            gender='Male',
            department=self.department,
            position='Operator',
            shift=self.shift,
            user=user,
            biometric_device='Phone',
            biometric_device_type='Mobile Phone',
            mobile_device_id='ANDROID-PIXEL-9',
            biometric_status='Enrolled',
        )

        self.client.force_login(user)
        response = self.client.post(reverse('attendance_check_in'), {'device_id': 'WRONG-DEVICE'})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Attendance.objects.filter(employee=employee, date=timezone.localdate()).exists())

    def test_attendance_page_shows_device_field_for_fingerprint_checkin(self):
        user = get_user_model().objects.create_user(username='fingerprint-ui-user', password='StrongPass123!')
        employee = Employee.objects.create(
            employee_id='EMP-2007',
            first_name='Ruby',
            last_name='Khan',
            gender='Female',
            department=self.department,
            position='Operator',
            shift=self.shift,
            user=user,
            biometric_device='Scanner',
            biometric_device_type='Fingerprint Scanner',
            biometric_id='FP-UI-001',
            biometric_status='Enrolled',
        )

        self.client.force_login(user)
        response = self.client.get(reverse('attendance_today'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="device_id"')
        self.assertContains(response, 'FP-UI-001')

    def test_fingerprint_biometric_check_in_requires_matching_biometric_id(self):
        user = get_user_model().objects.create_user(username='fingerprint-user-1', password='StrongPass123!')
        employee = Employee.objects.create(
            employee_id='EMP-2006',
            first_name='Ava',
            last_name='Patel',
            gender='Female',
            department=self.department,
            position='Operator',
            shift=self.shift,
            user=user,
            biometric_device='Scanner',
            biometric_device_type='Fingerprint Scanner',
            biometric_id='FP-1001',
            biometric_status='Enrolled',
        )

        self.client.force_login(user)
        response = self.client.post(reverse('attendance_check_in'), {'device_id': 'FP-1001'})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Attendance.objects.filter(employee=employee, date=timezone.localdate()).exists())

        attendance = Attendance.objects.get(employee=employee, date=timezone.localdate())
        self.assertEqual(attendance.verification_method, 'Fingerprint Scanner')
        self.assertEqual(attendance.verification_device_id, 'FP-1001')

        self.client.post(reverse('attendance_check_in'), {'device_id': 'WRONG-FINGERPRINT'})
        self.assertEqual(Attendance.objects.filter(employee=employee, date=timezone.localdate()).count(), 1)

    def test_check_in_creates_audit_log(self):
        user = get_user_model().objects.create_user(username='mobile-user-3', password='StrongPass123!')
        employee = Employee.objects.create(
            employee_id='EMP-2004',
            first_name='Tina',
            last_name='Ross',
            gender='Female',
            department=self.department,
            position='Operator',
            shift=self.shift,
            user=user,
            biometric_device='Phone',
            biometric_device_type='Mobile Phone',
            mobile_device_id='ANDROID-PIXEL-10',
            biometric_status='Enrolled',
        )

        self.client.force_login(user)
        self.client.post(reverse('attendance_check_in'), {'device_id': 'ANDROID-PIXEL-10'})

        self.assertTrue(AuditLog.objects.filter(model_name='Attendance', action='Checked in').exists())

    def test_overnight_attendance_can_check_out_after_midnight(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        self.shift = Shift.objects.create(
            name='Night',
            start_time='22:00:00',
            end_time='06:00:00',
            working_hours=8,
            is_overnight=True,
        )
        self.employee.shift = self.shift
        self.employee.mobile_device_id = 'NIGHT-SHIFT-DEVICE'
        self.employee.save(update_fields=['shift', 'mobile_device_id'])
        check_in = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()).replace(hour=22))
        check_out = timezone.make_aware(datetime.combine(today, datetime.min.time()).replace(hour=6))
        Attendance.objects.create(
            employee=self.employee,
            date=yesterday,
            check_in=check_in,
            status='Present',
        )
        self.client.force_login(self.user)

        with patch('attendance.views.timezone.now', return_value=check_out):
            response = self.client.post(
                reverse('attendance_check_out'),
                {'device_id': 'NIGHT-SHIFT-DEVICE'},
            )

        self.assertEqual(response.status_code, 302)
        record = Attendance.objects.get(employee=self.employee, date=yesterday)
        self.assertEqual(record.check_out, check_out)
        self.assertEqual(record.total_work_hours, Decimal('8.00'))

    def test_overnight_check_in_after_midnight_uses_previous_day(self):
        self.employee.biometric_device = 'Phone'
        self.employee.biometric_device_type = 'Mobile Phone'
        self.employee.mobile_device_id = 'NIGHT-SHIFT-DEVICE'
        self.employee.biometric_status = 'Enrolled'
        self.employee.shift = Shift.objects.create(
            name='Night',
            start_time='22:00:00',
            end_time='06:00:00',
            working_hours=8,
            is_overnight=True,
            grace_period_minutes=10,
            is_active=True,
        )
        self.employee.save(update_fields=['biometric_device', 'biometric_device_type', 'mobile_device_id', 'biometric_status', 'shift'])
        self.client.force_login(self.user)

        check_in = timezone.make_aware(datetime.combine(timezone.localdate(), datetime.min.time()).replace(hour=1))
        with patch('attendance.views.timezone.now', return_value=check_in):
            response = self.client.post(reverse('attendance_check_in'), {'device_id': 'NIGHT-SHIFT-DEVICE'})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Attendance.objects.filter(employee=self.employee, date=check_in.date() - timedelta(days=1)).exists())

    def test_leave_approval_creates_audit_log(self):
        user = get_user_model().objects.create_user(username='audit-leave-user', password='StrongPass123!')
        reviewer = get_user_model().objects.create_user(username='leave-reviewer', password='StrongPass123!')
        reviewer.groups.add(Group.objects.get_or_create(name='HR Staff')[0])
        employee = Employee.objects.create(
            employee_id='EMP-2005',
            first_name='June',
            last_name='Davis',
            gender='Female',
            department=self.department,
            position='Operator',
            shift=self.shift,
            user=user,
        )
        leave_request = LeaveRequest.objects.create(
            employee=employee,
            leave_type='Annual Leave',
            start_date='2026-11-01',
            end_date='2026-11-03',
            reason='Family leave',
            status='Pending',
        )

        self.client.force_login(reviewer)
        self.client.post(reverse('leave_approve', args=[leave_request.pk]))

        self.assertTrue(AuditLog.objects.filter(model_name='LeaveRequest', action='Approved leave').exists())


class LeaveRequestTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='leaveuser', password='StrongPass123!')
        self.department = Department.objects.create(name='Maintenance', code='MTN', description='Maintenance team')
        self.employee = Employee.objects.create(
            employee_id='EMP-3001',
            first_name='Maria',
            last_name='Lopez',
            gender='Female',
            department=self.department,
            position='Technician',
            user=self.user,
        )

    def test_leave_request_creation(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('leave_request_create'),
            {
                'leave_type': 'Annual Leave',
                'start_date': '2026-10-05',
                'end_date': '2026-10-07',
                'reason': 'Family trip',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(LeaveRequest.objects.filter(employee=self.employee, status='Pending').exists())

    def test_leave_request_approval(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type='Sick Leave',
            start_date='2026-10-10',
            end_date='2026-10-12',
            reason='Fever',
            status='Pending',
        )

        reviewer = get_user_model().objects.create_user(username='leave-reviewer', password='StrongPass123!')
        reviewer.groups.add(Group.objects.get_or_create(name='HR Staff')[0])
        self.client.force_login(reviewer)
        response = self.client.post(reverse('leave_approve', args=[leave_request.pk]))

        self.assertEqual(response.status_code, 302)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'Approved')
        self.assertEqual(leave_request.approved_by, reviewer)

    def test_employee_cannot_approve_leave_request(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type='Sick Leave',
            start_date='2026-10-10',
            end_date='2026-10-12',
            reason='Fever',
            status='Pending',
        )

        self.client.force_login(self.user)
        response = self.client.post(reverse('leave_approve', args=[leave_request.pk]))

        self.assertEqual(response.status_code, 403)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'Pending')

    def test_leave_request_rejects_end_date_before_start_date(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('leave_request_create'),
            {
                'leave_type': 'Annual Leave',
                'start_date': '2026-10-07',
                'end_date': '2026-10-05',
                'reason': 'Family trip',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(LeaveRequest.objects.filter(employee=self.employee).exists())


class ReportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='reportuser', password='StrongPass123!')
        self.user.groups.add(Group.objects.get_or_create(name='HR Staff')[0])
        self.department = Department.objects.create(name='Quality', code='QA', description='Quality control')
        self.shift = Shift.objects.create(
            name='Morning',
            start_time='08:00:00',
            end_time='17:00:00',
            grace_period_minutes=10,
            working_hours=8.00,
            is_active=True,
        )
        self.employee = Employee.objects.create(
            employee_id='EMP-4001',
            first_name='Daniel',
            last_name='Green',
            gender='Male',
            department=self.department,
            position='Auditor',
            shift=self.shift,
            user=self.user,
        )
        Attendance.objects.create(
            employee=self.employee,
            date='2026-10-01',
            check_in=timezone.make_aware(datetime(2026, 10, 1, 8, 0)),
            check_out=timezone.make_aware(datetime(2026, 10, 1, 17, 0)),
            status='Present',
            late_minutes=0,
            total_work_hours=9.00,
            overtime_hours=1.00,
        )

    def test_reports_page_renders(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reports'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Daily Attendance Report')

    def test_csv_report_export(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reports_export_csv'), {'report_type': 'daily', 'date': '2026-10-01'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertContains(response, 'employee')
        self.assertContains(response, 'Daniel')


class AuditLogTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='audit-admin', password='StrongPass123!')
        self.employee_user = get_user_model().objects.create_user(username='audit-employee', password='StrongPass123!')
        self.admin_group, _ = Group.objects.get_or_create(name='HR Administrator')
        self.user.groups.add(self.admin_group)

    def test_audit_log_page_rejects_regular_employees(self):
        self.client.force_login(self.employee_user)

        response = self.client.get(reverse('audit_log_list'))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_filter_audit_logs(self):
        AuditLog.objects.create(
            actor=self.user,
            action='Approved leave',
            model_name='LeaveRequest',
            object_id='17',
            details='Approved leave for Alex.',
        )
        AuditLog.objects.create(
            actor=self.user,
            action='Checked in',
            model_name='Attendance',
            object_id='24',
            details='Alex checked in using Mobile Phone.',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('audit_log_list'), {'model': 'LeaveRequest'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj'].object_list), 1)
        self.assertEqual(response.context['page_obj'].object_list[0].model_name, 'LeaveRequest')
        self.assertContains(response, 'Approved leave')


class UserManagementTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_user(username='role-admin', password='StrongPass123!')
        self.employee_user = get_user_model().objects.create_user(username='role-employee', password='StrongPass123!')
        self.hr_group, _ = Group.objects.get_or_create(name='HR Administrator')
        self.employee_group, _ = Group.objects.get_or_create(name='Employee')
        self.admin_user.groups.add(self.hr_group)

    def test_user_management_rejects_regular_employees(self):
        self.client.force_login(self.employee_user)

        response = self.client.get(reverse('user_management'))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_assign_group_roles(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('user_management'),
            {'user_id': self.employee_user.pk, 'groups': [str(self.hr_group.pk), str(self.employee_group.pk)]},
        )

        self.assertEqual(response.status_code, 302)
        self.employee_user.refresh_from_db()
        self.assertTrue(self.employee_user.groups.filter(pk=self.hr_group.pk).exists())
        self.assertTrue(self.employee_user.groups.filter(pk=self.employee_group.pk).exists())

    def test_registration_creates_an_inactive_account(self):
        response = self.client.post(reverse('register'), {
            'username': 'new-staff',
            'first_name': 'New',
            'last_name': 'Staff',
            'email': 'new.staff@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })

        self.assertRedirects(response, reverse('login'))
        user = get_user_model().objects.get(username='new-staff')
        self.assertFalse(user.is_active)
        self.assertEqual(user.email, 'new.staff@example.com')
        self.assertFalse(self.client.login(username='new-staff', password='StrongPass123!'))

    def test_hr_admin_can_approve_pending_account(self):
        pending_user = get_user_model().objects.create_user(
            username='pending-staff',
            password='StrongPass123!',
            is_active=False,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse('approve_user', args=[pending_user.pk]))

        self.assertRedirects(response, reverse('user_management'))
        pending_user.refresh_from_db()
        self.assertTrue(pending_user.is_active)
        self.assertTrue(self.client.login(username='pending-staff', password='StrongPass123!'))

    def test_regular_user_cannot_approve_pending_account(self):
        pending_user = get_user_model().objects.create_user(
            username='pending-staff',
            password='StrongPass123!',
            is_active=False,
        )
        self.client.force_login(self.employee_user)

        response = self.client.post(reverse('approve_user', args=[pending_user.pk]))

        self.assertEqual(response.status_code, 403)
        pending_user.refresh_from_db()
        self.assertFalse(pending_user.is_active)


class HolidayManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='holiday-admin', password='StrongPass123!')
        self.hr_group, _ = Group.objects.get_or_create(name='HR Administrator')
        self.user.groups.add(self.hr_group)

    def test_holiday_page_requires_login(self):
        response = self.client.get(reverse('holiday_list'))
        self.assertEqual(response.status_code, 302)

    def test_holiday_creation(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('holiday_create'),
            {
                'name': 'Eid Al Fitr',
                'holiday_date': '2026-03-31',
                'description': 'Public holiday',
                'is_recurring': True,
                'is_active': True,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Holiday.objects.filter(name='Eid Al Fitr', holiday_date='2026-03-31').exists())


class OvertimeManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='overtime-admin', password='StrongPass123!')
        self.employee_user = get_user_model().objects.create_user(username='overtime-employee', password='StrongPass123!')
        self.department = Department.objects.create(name='Production', code='PROD', description='Production line')
        self.employee = Employee.objects.create(
            employee_id='EMP-9001',
            first_name='Noah',
            last_name='Brown',
            gender='Male',
            department=self.department,
            position='Operator',
            user=self.employee_user,
        )
        self.hr_group, _ = Group.objects.get_or_create(name='HR Administrator')
        self.user.groups.add(self.hr_group)

    def test_overtime_page_requires_login(self):
        response = self.client.get(reverse('overtime_list'))
        self.assertEqual(response.status_code, 302)

    def test_overtime_submission_and_approval(self):
        self.client.force_login(self.employee_user)
        response = self.client.post(
            reverse('overtime_request_create'),
            {
                'employee': self.employee.pk,
                'date': '2026-11-02',
                'hours': 2.5,
                'reason': 'Night shift support',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(OvertimeRequest.objects.filter(employee=self.employee, hours=2.5).exists())

        overtime_request = OvertimeRequest.objects.get(employee=self.employee, hours=2.5)
        self.client.force_login(self.user)
        response = self.client.post(reverse('overtime_approve', args=[overtime_request.pk]))

        self.assertEqual(response.status_code, 302)
        overtime_request.refresh_from_db()
        self.assertEqual(overtime_request.status, 'Approved')
