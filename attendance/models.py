from datetime import datetime, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class Shift(models.Model):
    name = models.CharField(max_length=80)
    start_time = models.TimeField()
    end_time = models.TimeField()
    grace_period_minutes = models.PositiveIntegerField(default=10)
    working_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8.00)
    is_overnight = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return self.name

    def calculate_checkin_status(self, check_in_time):
        aware_time = timezone.make_aware(check_in_time) if timezone.is_naive(check_in_time) else check_in_time
        target_date = aware_time.date()

        start_value = self.start_time
        if isinstance(start_value, str):
            start_value = datetime.strptime(start_value, '%H:%M:%S').time()

        if self.is_overnight:
            shift_start = timezone.make_aware(datetime.combine(target_date, start_value))
            if shift_start > aware_time:
                shift_start = shift_start - timedelta(days=1)
        else:
            shift_start = timezone.make_aware(datetime.combine(target_date, start_value))

        late_minutes = max(0, int((aware_time - shift_start).total_seconds() // 60) - int(self.grace_period_minutes))
        status = 'Late' if late_minutes > 0 else 'Present'
        return status, late_minutes

    def calculate_work_duration(self, check_in_time, check_out_time):
        aware_check_in = timezone.make_aware(check_in_time) if timezone.is_naive(check_in_time) else check_in_time
        aware_check_out = timezone.make_aware(check_out_time) if timezone.is_naive(check_out_time) else check_out_time

        if self.is_overnight and aware_check_out.date() == aware_check_in.date():
            aware_check_out = aware_check_out + timedelta(days=1)

        duration_minutes = max(0, (aware_check_out - aware_check_in).total_seconds() / 60)
        total_hours = round(duration_minutes / 60, 2)
        overtime_hours = max(0, round(total_hours - float(self.working_hours), 2))
        return total_hours, overtime_hours


class Employee(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    EMPLOYMENT_STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Resigned', 'Resigned'),
        ('Terminated', 'Terminated'),
        ('On Leave', 'On Leave'),
    ]

    employee_id = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=80)
    middle_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=150, blank=True)
    address = models.TextField(blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
    )
    position = models.CharField(max_length=120, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    employment_status = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_STATUS_CHOICES,
        default='Active',
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
    )
    biometric_id = models.CharField(max_length=80, blank=True, default='')
    biometric_device = models.CharField(max_length=120, blank=True, default='')
    biometric_device_type = models.CharField(
        max_length=30,
        choices=[
            ('Mobile Phone', 'Mobile Phone'),
            ('Fingerprint Scanner', 'Fingerprint Scanner'),
            ('RFID Reader', 'RFID Reader'),
            ('Other', 'Other'),
        ],
        default='Mobile Phone',
    )
    mobile_device_id = models.CharField(max_length=120, blank=True, default='')
    biometric_status = models.CharField(
        max_length=20,
        choices=[
            ('Not Enrolled', 'Not Enrolled'),
            ('Pending', 'Pending'),
            ('Enrolled', 'Enrolled'),
        ],
        default='Not Enrolled',
    )
    biometric_notes = models.TextField(blank=True)
    profile_photo = models.ImageField(upload_to='profiles/', blank=True, null=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_profile',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.employee_id})'


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Late', 'Late'),
        ('Absent', 'Absent'),
        ('Half Day', 'Half Day'),
        ('Leave', 'Leave'),
        ('Holiday', 'Holiday'),
        ('Weekend', 'Weekend'),
    ]

    VERIFICATION_CHOICES = [
        ('Manual', 'Manual'),
        ('Mobile Phone', 'Mobile Phone'),
        ('Fingerprint Scanner', 'Fingerprint Scanner'),
        ('RFID Reader', 'RFID Reader'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Present')
    verification_method = models.CharField(max_length=30, choices=VERIFICATION_CHOICES, default='Manual')
    verification_device_id = models.CharField(max_length=120, blank=True, default='')
    late_minutes = models.PositiveIntegerField(default=0)
    early_leave_minutes = models.PositiveIntegerField(default=0)
    total_work_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.employee} - {self.date} - {self.status}'


class LeaveRequest(models.Model):
    LEAVE_TYPE_CHOICES = [
        ('Annual Leave', 'Annual Leave'),
        ('Sick Leave', 'Sick Leave'),
        ('Permission', 'Permission'),
        ('Maternity Leave', 'Maternity Leave'),
        ('Paternity Leave', 'Paternity Leave'),
        ('Unpaid Leave', 'Unpaid Leave'),
        ('Other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=30, choices=LEAVE_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leave_requests',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee} - {self.leave_type} - {self.status}'


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=120)
    model_name = models.CharField(max_length=80)
    object_id = models.CharField(max_length=50, blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} - {self.model_name}'


class OvertimeRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='overtime_requests')
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_overtime_requests',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.employee} - {self.date} - {self.hours} hours'


class Holiday(models.Model):
    name = models.CharField(max_length=120)
    holiday_date = models.DateField()
    description = models.TextField(blank=True)
    is_recurring = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['holiday_date']
        unique_together = ('name', 'holiday_date')

    def __str__(self):
        return f'{self.name} ({self.holiday_date})'
