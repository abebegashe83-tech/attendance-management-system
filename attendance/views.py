import csv
from calendar import monthrange
from decimal import Decimal
from datetime import datetime, timedelta
from io import StringIO

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import DepartmentForm, EmployeeForm, HolidayForm, LeaveRequestForm, OvertimeRequestForm, RegistrationForm, ShiftForm
from .models import Attendance, AuditLog, Department, Employee, Holiday, LeaveRequest, OvertimeRequest, Shift
from .permissions import (
    user_can_review_all_requests,
    user_can_review_request,
    user_can_view_reports,
    user_has_role,
)


def create_audit_log(actor, action, model_name, object_id='', details=''):
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        model_name=model_name,
        object_id=str(object_id),
        details=details,
    )


def registration(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Your account request has been submitted. You can sign in after an administrator approves it.',
            )
            return redirect('login')
    else:
        form = RegistrationForm()

    return render(request, 'registration/register.html', {'form': form})


def get_biometric_verification(employee, device_id):
    device_type = employee.biometric_device_type
    expected_device_id = ''
    verification_method = 'Manual'

    if device_type == 'Mobile Phone':
        expected_device_id = employee.mobile_device_id
        verification_method = 'Mobile Phone'
    elif device_type in {'Fingerprint Scanner', 'RFID Reader'}:
        expected_device_id = employee.biometric_id
        verification_method = device_type

    if not expected_device_id:
        return False, verification_method, 'This employee is not configured for biometric check-in.'

    if not device_id or device_id != expected_device_id:
        return False, verification_method, 'Biometric verification failed. The registered device ID does not match.'

    return True, verification_method, ''


def get_attendance_date_for_shift(shift, timestamp):
    if not shift or not getattr(shift, 'is_overnight', False):
        return timestamp.date()

    if timestamp.time() < shift.start_time:
        return timestamp.date() - timedelta(days=1)
    return timestamp.date()


@login_required(login_url='login')
def dashboard(request):
    today = timezone.localdate()
    total_employees = Employee.objects.filter(employment_status='Active').count()
    present_count = Attendance.objects.filter(date=today, status='Present').count()
    late_count = Attendance.objects.filter(date=today, status='Late').count()
    checked_in_count = Attendance.objects.filter(date=today).count()

    if total_employees:
        attendance_rate = round(((present_count + late_count) / total_employees) * 100, 1)
    else:
        attendance_rate = 0

    recent_attendance = Attendance.objects.select_related('employee__department').filter(date=today).order_by('-check_in')[:5]
    pending_leave_count = LeaveRequest.objects.filter(status='Pending').count()
    recent_leaves = LeaveRequest.objects.select_related('employee__department').filter(
        status='Pending',
    ).order_by('-created_at')[:5]

    department_summary = Department.objects.annotate(
        present=Count('employees__attendance_records', filter=Q(employees__attendance_records__date=today, employees__attendance_records__status='Present')),
        late=Count('employees__attendance_records', filter=Q(employees__attendance_records__date=today, employees__attendance_records__status='Late')),
    )

    department_summary = list(department_summary)
    for dept in department_summary:
        dept.total_staff = Employee.objects.filter(department=dept, employment_status='Active').count()
        dept.checked_in = Attendance.objects.filter(employee__department=dept, date=today).count()
        dept.absent = max(0, dept.total_staff - dept.checked_in)

    late_employees = Attendance.objects.select_related('employee__department').filter(date=today, status='Late')[:5]
    absent_employees = Employee.objects.filter(employment_status='Active').exclude(attendance_records__date=today).order_by('last_name', 'first_name')[:5]

    return render(request, 'attendance/dashboard.html', {
        'title': 'Dashboard',
        'today': today,
        'total_employees': total_employees,
        'present_count': present_count,
        'late_count': late_count,
        'checked_in_count': checked_in_count,
        'pending_leave_count': pending_leave_count,
        'attendance_rate': attendance_rate,
        'recent_attendance': recent_attendance,
        'recent_leaves': recent_leaves,
        'department_summary': department_summary,
        'late_employees': late_employees,
        'absent_employees': absent_employees,
    })


@login_required(login_url='login')
def employee_list(request):
    employees = Employee.objects.select_related('department', 'shift', 'user').order_by('last_name', 'first_name')
    query = request.GET.get('q', '').strip()

    if query:
        employees = employees.filter(
            Q(employee_id__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(department__name__icontains=query)
            | Q(position__icontains=query)
        )

    paginator = Paginator(employees, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'attendance/employee_list.html', {
        'page_obj': page_obj,
        'query': query,
    })


@login_required(login_url='login')
def employee_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    return render(request, 'attendance/employee_detail.html', {'employee': employee})


@login_required(login_url='login')
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES)
        if form.is_valid():
            employee = form.save()
            create_audit_log(
                request.user,
                'Created employee',
                'Employee',
                employee.pk,
                f'Employee {employee} was created.',
            )
            messages.success(request, 'Employee created successfully.')
            return redirect('employee_list')
    else:
        form = EmployeeForm()

    return render(request, 'attendance/employee_form.html', {'form': form, 'title': 'Add Employee'})


@login_required(login_url='login')
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)

    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            employee = form.save()
            create_audit_log(
                request.user,
                'Updated employee',
                'Employee',
                employee.pk,
                f'Employee {employee} was updated.',
            )
            messages.success(request, 'Employee updated successfully.')
            return redirect('employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee)

    return render(request, 'attendance/employee_form.html', {'form': form, 'title': 'Edit Employee', 'employee': employee})


@login_required(login_url='login')
def employee_deactivate(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        employee.employment_status = 'Inactive'
        employee.save(update_fields=['employment_status', 'updated_at'])
        messages.success(request, f'{employee.first_name} {employee.last_name} has been deactivated.')
        return redirect('employee_list')
    return render(request, 'attendance/employee_detail.html', {'employee': employee})


@login_required(login_url='login')
def department_list(request):
    departments = Department.objects.select_related('manager').order_by('name')
    query = request.GET.get('q', '').strip()
    if query:
        departments = departments.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(description__icontains=query)
        )
    paginator = Paginator(departments, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'attendance/department_list.html', {'page_obj': page_obj, 'query': query})


@login_required(login_url='login')
def department_detail(request, pk):
    department = get_object_or_404(Department, pk=pk)
    employee_count = department.employees.count()
    return render(request, 'attendance/department_detail.html', {'department': department, 'employee_count': employee_count})


@login_required(login_url='login')
def department_create(request):
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Department created successfully.')
            return redirect('department_list')
    else:
        form = DepartmentForm()
    return render(request, 'attendance/department_form.html', {'form': form, 'title': 'Add Department'})


@login_required(login_url='login')
def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, 'Department updated successfully.')
            return redirect('department_detail', pk=department.pk)
    else:
        form = DepartmentForm(instance=department)
    return render(request, 'attendance/department_form.html', {'form': form, 'title': 'Edit Department', 'department': department})


@login_required(login_url='login')
def shift_list(request):
    shifts = Shift.objects.order_by('start_time')
    query = request.GET.get('q', '').strip()
    if query:
        shifts = shifts.filter(Q(name__icontains=query) | Q(start_time__icontains=query))
    paginator = Paginator(shifts, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'attendance/shift_list.html', {'page_obj': page_obj, 'query': query})


@login_required(login_url='login')
def shift_detail(request, pk):
    shift = get_object_or_404(Shift, pk=pk)
    return render(request, 'attendance/shift_detail.html', {'shift': shift})


@login_required(login_url='login')
def shift_create(request):
    if request.method == 'POST':
        form = ShiftForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Shift created successfully.')
            return redirect('shift_list')
    else:
        form = ShiftForm()
    return render(request, 'attendance/shift_form.html', {'form': form, 'title': 'Add Shift'})


@login_required(login_url='login')
def shift_edit(request, pk):
    shift = get_object_or_404(Shift, pk=pk)
    if request.method == 'POST':
        form = ShiftForm(request.POST, instance=shift)
        if form.is_valid():
            form.save()
            messages.success(request, 'Shift updated successfully.')
            return redirect('shift_detail', pk=shift.pk)
    else:
        form = ShiftForm(instance=shift)
    return render(request, 'attendance/shift_form.html', {'form': form, 'title': 'Edit Shift', 'shift': shift})


@login_required(login_url='login')
def leave_list(request):
    employee = getattr(request.user, 'employee_profile', None)
    leave_requests = LeaveRequest.objects.select_related('employee__department', 'approved_by')

    if user_can_review_all_requests(request.user):
        pass
    elif user_has_role(request.user, 'Department Manager'):
        leave_requests = leave_requests.filter(employee__department__manager=request.user)
    elif employee:
        leave_requests = leave_requests.filter(employee=employee)
    else:
        return HttpResponseForbidden('You do not have permission to view leave requests.')

    query = request.GET.get('q', '').strip()
    if query:
        leave_requests = leave_requests.filter(
            Q(employee__first_name__icontains=query)
            | Q(employee__last_name__icontains=query)
            | Q(leave_type__icontains=query)
            | Q(status__icontains=query)
        )

    paginator = Paginator(leave_requests, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'attendance/leave_list.html', {
        'page_obj': page_obj,
        'query': query,
        'employee': employee,
        'can_review_requests': user_can_review_all_requests(request.user) or user_has_role(request.user, 'Department Manager'),
        'today': timezone.localdate(),
    })


@login_required(login_url='login')
def reports(request):
    if not user_can_view_reports(request.user):
        return HttpResponseForbidden('You do not have permission to view attendance reports.')

    report_type = request.GET.get('report_type', 'daily')
    selected_date = request.GET.get('date', timezone.localdate().isoformat())
    selected_month = request.GET.get('month', timezone.localdate().strftime('%Y-%m'))

    try:
        date_value = timezone.datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        date_value = timezone.localdate()

    attendance_queryset = Attendance.objects.select_related('employee__department')
    if user_has_role(request.user, 'Department Manager') and not user_can_review_all_requests(request.user):
        attendance_queryset = attendance_queryset.filter(employee__department__manager=request.user)

    if report_type == 'monthly':
        report_rows = attendance_queryset.filter(date__year=date_value.year, date__month=date_value.month).order_by('employee__last_name', 'employee__first_name')
        summary = {
            'total_days': report_rows.count(),
            'present': report_rows.filter(status='Present').count(),
            'late': report_rows.filter(status='Late').count(),
            'absent': report_rows.filter(status='Absent').count(),
        }
        report_title = 'Monthly Attendance Report'
    elif report_type == 'employee':
        report_rows = attendance_queryset.order_by('-date')[:20]
        summary = {'present': report_rows.filter(status='Present').count()}
        report_title = 'Employee Attendance Report'
    elif report_type == 'department':
        report_rows = attendance_queryset.order_by('employee__department__name', '-date')[:20]
        summary = {'present': report_rows.filter(status='Present').count()}
        report_title = 'Department Attendance Report'
    else:
        report_rows = attendance_queryset.filter(date=date_value).order_by('-check_in')
        summary = {
            'total': report_rows.count(),
            'present': report_rows.filter(status='Present').count(),
            'late': report_rows.filter(status='Late').count(),
            'absent': report_rows.filter(status='Absent').count(),
        }
        report_title = 'Daily Attendance Report'

    return render(request, 'attendance/reports.html', {
        'report_type': report_type,
        'selected_date': selected_date,
        'selected_month': selected_month,
        'report_rows': report_rows,
        'summary': summary,
        'report_title': report_title,
    })


@login_required(login_url='login')
def reports_export_csv(request):
    if not user_can_view_reports(request.user):
        return HttpResponseForbidden('You do not have permission to export attendance reports.')

    report_type = request.GET.get('report_type', 'daily')
    selected_date = request.GET.get('date', timezone.localdate().isoformat())

    try:
        date_value = timezone.datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        date_value = timezone.localdate()

    attendance_queryset = Attendance.objects.select_related('employee__department')
    if user_has_role(request.user, 'Department Manager') and not user_can_review_all_requests(request.user):
        attendance_queryset = attendance_queryset.filter(employee__department__manager=request.user)

    if report_type == 'monthly':
        queryset = attendance_queryset.filter(date__year=date_value.year, date__month=date_value.month).order_by('employee__last_name', 'employee__first_name')
    elif report_type == 'employee':
        queryset = attendance_queryset.order_by('-date')[:20]
    elif report_type == 'department':
        queryset = attendance_queryset.order_by('employee__department__name', '-date')[:20]
    else:
        queryset = attendance_queryset.filter(date=date_value).order_by('-check_in')

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['employee', 'department', 'date', 'status', 'check_in', 'check_out', 'total_work_hours', 'overtime_hours'])

    for record in queryset:
        writer.writerow([
            str(record.employee),
            record.employee.department.name if record.employee.department else '',
            record.date,
            record.status,
            record.check_in.strftime('%Y-%m-%d %H:%M:%S') if record.check_in else '',
            record.check_out.strftime('%Y-%m-%d %H:%M:%S') if record.check_out else '',
            record.total_work_hours,
            record.overtime_hours,
        ])

    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'
    return response


@login_required(login_url='login')
def payroll_summary(request):
    selected_month = request.GET.get('month', timezone.localdate().strftime('%Y-%m'))

    try:
        year, month = map(int, selected_month.split('-'))
        month_start = datetime(year, month, 1).date()
    except (TypeError, ValueError):
        month_start = timezone.localdate().replace(day=1)

    total_days_in_month = monthrange(month_start.year, month_start.month)[1]
    employees = Employee.objects.filter(employment_status='Active').select_related('department')

    payroll_rows = []
    total_present_days = 0
    total_leave_days = 0
    total_work_hours = Decimal('0')
    total_overtime_hours = Decimal('0')

    for employee in employees:
        attendance = Attendance.objects.filter(
            employee=employee,
            date__year=month_start.year,
            date__month=month_start.month,
        )
        present_days = attendance.filter(status__in=['Present', 'Late']).count()
        leave_days = attendance.filter(status='Leave').count()
        absent_days = total_days_in_month - (present_days + leave_days)
        if absent_days < 0:
            absent_days = 0

        work_hours = attendance.aggregate(total=Sum('total_work_hours'))['total'] or Decimal('0')
        overtime_hours = attendance.aggregate(total=Sum('overtime_hours'))['total'] or Decimal('0')

        total_present_days += present_days
        total_leave_days += leave_days
        total_work_hours += work_hours
        total_overtime_hours += overtime_hours

        payroll_rows.append({
            'employee': employee,
            'department': employee.department.name if employee.department else '--',
            'present_days': present_days,
            'leave_days': leave_days,
            'absent_days': absent_days,
            'work_hours': work_hours,
            'overtime_hours': overtime_hours,
        })

    return render(request, 'attendance/payroll_summary.html', {
        'selected_month': selected_month,
        'month_start': month_start,
        'payroll_rows': payroll_rows,
        'summary': {
            'employees': employees.count(),
            'present_days': total_present_days,
            'leave_days': total_leave_days,
            'work_hours': total_work_hours,
            'overtime_hours': total_overtime_hours,
        },
    })


@login_required(login_url='login')
def user_management(request):
    allowed_roles = ('Super Administrator', 'HR Administrator', 'IT Administrator')
    if not request.user.is_superuser and not any(user_has_role(request.user, role) for role in allowed_roles):
        return HttpResponseForbidden('You do not have permission to manage user roles.')

    User = get_user_model()
    users = User.objects.prefetch_related('groups').order_by('username')
    selected_user = None
    available_groups = Group.objects.order_by('name')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        selected_user = get_object_or_404(User, pk=user_id) if user_id else None
        group_ids = request.POST.getlist('groups')
        if selected_user:
            selected_user.groups.set(Group.objects.filter(pk__in=group_ids))
            messages.success(request, f'Roles updated for {selected_user.username}.')
            return redirect('user_management')

    if request.GET.get('user_id'):
        selected_user = get_object_or_404(User, pk=request.GET.get('user_id'))

    return render(request, 'attendance/user_management.html', {
        'users': users,
        'pending_users': User.objects.filter(is_active=False).order_by('date_joined'),
        'selected_user': selected_user,
        'available_groups': available_groups,
    })


@login_required(login_url='login')
@require_POST
def approve_user(request, pk):
    allowed_roles = ('Super Administrator', 'HR Administrator', 'IT Administrator')
    if not request.user.is_superuser and not any(user_has_role(request.user, role) for role in allowed_roles):
        return HttpResponseForbidden('You do not have permission to approve user accounts.')

    User = get_user_model()
    user = get_object_or_404(User, pk=pk, is_active=False)
    user.is_active = True
    user.save(update_fields=['is_active'])
    create_audit_log(
        request.user,
        'Approved user account',
        'User',
        user.pk,
        f'Account for {user.username} was approved.',
    )
    messages.success(request, f'{user.username} can now sign in.')
    return redirect('user_management')


@login_required(login_url='login')
def holiday_list(request):
    holidays = Holiday.objects.order_by('holiday_date')
    query = request.GET.get('q', '').strip()
    if query:
        holidays = holidays.filter(Q(name__icontains=query) | Q(description__icontains=query))
    return render(request, 'attendance/holiday_list.html', {'holidays': holidays, 'query': query})


@login_required(login_url='login')
def holiday_create(request):
    if request.method == 'POST':
        form = HolidayForm(request.POST)
        if form.is_valid():
            holiday = form.save()
            create_audit_log(
                request.user,
                'Created holiday',
                'Holiday',
                holiday.pk,
                f'{holiday.name} was added to the holiday calendar.',
            )
            messages.success(request, 'Holiday created successfully.')
            return redirect('holiday_list')
    else:
        form = HolidayForm()
    return render(request, 'attendance/holiday_form.html', {'form': form, 'title': 'Add Holiday'})


@login_required(login_url='login')
def overtime_list(request):
    employee = getattr(request.user, 'employee_profile', None)
    overtime_requests = OvertimeRequest.objects.select_related('employee__department', 'approved_by').order_by('-date')

    if user_can_review_all_requests(request.user):
        pass
    elif user_has_role(request.user, 'Department Manager'):
        overtime_requests = overtime_requests.filter(employee__department__manager=request.user)
    elif employee:
        overtime_requests = overtime_requests.filter(employee=employee)
    else:
        return HttpResponseForbidden('You do not have permission to view overtime requests.')

    return render(request, 'attendance/overtime_list.html', {
        'page_obj': overtime_requests,
        'employee': employee,
        'can_review_requests': user_can_review_all_requests(request.user) or user_has_role(request.user, 'Department Manager'),
    })


@login_required(login_url='login')
def overtime_request_create(request):
    employee = getattr(request.user, 'employee_profile', None)
    if not employee:
        return HttpResponseForbidden('An employee profile is required to request overtime.')

    if request.method == 'POST':
        form = OvertimeRequestForm(request.POST, employee=employee)
        if form.is_valid():
            overtime_request = form.save(commit=False)
            if employee:
                overtime_request.employee = employee
            overtime_request.status = 'Pending'
            overtime_request.approved_by = None
            overtime_request.approved_at = None
            overtime_request.save()
            create_audit_log(
                request.user,
                'Requested overtime',
                'OvertimeRequest',
                overtime_request.pk,
                f'{overtime_request.employee} requested {overtime_request.hours} overtime hours.',
            )
            messages.success(request, 'Overtime request submitted successfully.')
            return redirect('overtime_list')
    else:
        form = OvertimeRequestForm(employee=employee)

    return render(request, 'attendance/overtime_form.html', {'form': form, 'title': 'Request Overtime'})


@login_required(login_url='login')
@require_POST
def overtime_approve(request, pk):
    overtime_request = get_object_or_404(OvertimeRequest, pk=pk)
    if not user_can_review_request(request.user, overtime_request.employee):
        return HttpResponseForbidden('You do not have permission to review this overtime request.')
    if overtime_request.status != 'Pending':
        messages.error(request, 'Only pending overtime requests can be reviewed.')
        return redirect('overtime_list')
    if request.method == 'POST':
        overtime_request.status = 'Approved'
        overtime_request.approved_by = request.user
        overtime_request.approved_at = timezone.now()
        overtime_request.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
        create_audit_log(
            request.user,
            'Approved overtime',
            'OvertimeRequest',
            overtime_request.pk,
            f'{overtime_request.employee} overtime request was approved.',
        )
        messages.success(request, 'Overtime request approved.')
    return redirect('overtime_list')


@login_required(login_url='login')
@require_POST
def overtime_reject(request, pk):
    overtime_request = get_object_or_404(OvertimeRequest, pk=pk)
    if not user_can_review_request(request.user, overtime_request.employee):
        return HttpResponseForbidden('You do not have permission to review this overtime request.')
    if overtime_request.status != 'Pending':
        messages.error(request, 'Only pending overtime requests can be reviewed.')
        return redirect('overtime_list')
    if request.method == 'POST':
        overtime_request.status = 'Rejected'
        overtime_request.approved_by = request.user
        overtime_request.approved_at = timezone.now()
        overtime_request.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
        create_audit_log(
            request.user,
            'Rejected overtime',
            'OvertimeRequest',
            overtime_request.pk,
            f'{overtime_request.employee} overtime request was rejected.',
        )
        messages.success(request, 'Overtime request rejected.')
    return redirect('overtime_list')


@login_required(login_url='login')
def audit_log_list(request):
    allowed_roles = ('Super Administrator', 'HR Administrator', 'IT Administrator')
    if not request.user.is_superuser and not any(user_has_role(request.user, role) for role in allowed_roles):
        return HttpResponseForbidden('You do not have permission to view audit logs.')

    logs = AuditLog.objects.select_related('actor').order_by('-created_at')
    selected_model = request.GET.get('model', '').strip()
    selected_action = request.GET.get('action', '').strip()
    query = request.GET.get('q', '').strip()

    if selected_model:
        logs = logs.filter(model_name=selected_model)
    if selected_action:
        logs = logs.filter(action=selected_action)
    if query:
        logs = logs.filter(
            Q(actor__username__icontains=query)
            | Q(actor__first_name__icontains=query)
            | Q(actor__last_name__icontains=query)
            | Q(details__icontains=query)
            | Q(object_id__icontains=query)
        )

    page_obj = Paginator(logs, 25).get_page(request.GET.get('page'))
    return render(request, 'attendance/audit_log_list.html', {
        'page_obj': page_obj,
        'selected_model': selected_model,
        'selected_action': selected_action,
        'query': query,
        'models': AuditLog.objects.order_by('model_name').values_list('model_name', flat=True).distinct(),
        'actions': AuditLog.objects.order_by('action').values_list('action', flat=True).distinct(),
    })


@login_required(login_url='login')
def leave_request_create(request):
    employee = getattr(request.user, 'employee_profile', None)
    if not employee:
        return HttpResponseForbidden('An employee profile is required to request leave.')

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, employee=employee)
        if form.is_valid():
            leave_request = form.save(commit=False)
            if employee:
                leave_request.employee = employee
            leave_request.status = 'Pending'
            leave_request.approved_by = None
            leave_request.approved_at = None
            leave_request.save()
            create_audit_log(
                request.user,
                'Submitted leave',
                'LeaveRequest',
                leave_request.pk,
                f'Leave request submitted for {leave_request.employee}.',
            )
            messages.success(request, 'Leave request submitted successfully.')
            return redirect('leave_list')
    else:
        form = LeaveRequestForm(employee=employee)

    return render(request, 'attendance/leave_form.html', {
        'form': form,
        'title': 'Apply Leave',
    })


@login_required(login_url='login')
@require_POST
def leave_approve(request, pk):
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    if not user_can_review_request(request.user, leave_request.employee):
        return HttpResponseForbidden('You do not have permission to review this leave request.')
    if leave_request.status != 'Pending':
        messages.error(request, 'Only pending leave requests can be reviewed.')
        return redirect('leave_list')
    if request.method == 'POST':
        leave_request.status = 'Approved'
        leave_request.approved_by = request.user
        leave_request.approved_at = timezone.now()
        leave_request.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
        create_audit_log(
            request.user,
            'Approved leave',
            'LeaveRequest',
            leave_request.pk,
            f'Leave request for {leave_request.employee} was approved.',
        )
        messages.success(request, 'Leave request approved.')
    return redirect('leave_list')


@login_required(login_url='login')
@require_POST
def leave_reject(request, pk):
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    if not user_can_review_request(request.user, leave_request.employee):
        return HttpResponseForbidden('You do not have permission to review this leave request.')
    if leave_request.status != 'Pending':
        messages.error(request, 'Only pending leave requests can be reviewed.')
        return redirect('leave_list')
    if request.method == 'POST':
        leave_request.status = 'Rejected'
        leave_request.approved_by = request.user
        leave_request.approved_at = timezone.now()
        leave_request.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
        create_audit_log(
            request.user,
            'Rejected leave',
            'LeaveRequest',
            leave_request.pk,
            f'Leave request for {leave_request.employee} was rejected.',
        )
        messages.success(request, 'Leave request rejected.')
    return redirect('leave_list')


@login_required(login_url='login')
@require_POST
def leave_cancel(request, pk):
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    if leave_request.employee.user_id != request.user.pk:
        return HttpResponseForbidden('You can only cancel your own leave requests.')
    if leave_request.status != 'Pending' and not (
        leave_request.status == 'Approved' and leave_request.start_date >= timezone.localdate()
    ):
        messages.error(request, 'This leave request can no longer be cancelled.')
        return redirect('leave_list')
    if request.method == 'POST':
        leave_request.status = 'Cancelled'
        leave_request.save(update_fields=['status', 'updated_at'])
        create_audit_log(
            request.user,
            'Cancelled leave',
            'LeaveRequest',
            leave_request.pk,
            f'Leave request for {leave_request.employee} was cancelled.',
        )
        messages.success(request, 'Leave request cancelled.')
    return redirect('leave_list')


@login_required(login_url='login')
def attendance_today(request):
    today = timezone.localdate()
    records = Attendance.objects.select_related('employee__department', 'employee__shift').filter(date=today).order_by('-check_in')
    employee = getattr(request.user, 'employee_profile', None)
    employee_record = None

    if employee:
        employee_record = Attendance.objects.filter(employee=employee, date=today).first()

    return render(request, 'attendance/attendance_today.html', {
        'records': records,
        'employee_record': employee_record,
        'employee': employee,
    })


@login_required(login_url='login')
@require_POST
def attendance_check_in(request):
    employee = getattr(request.user, 'employee_profile', None)
    if not employee:
        messages.error(request, 'This account is not linked to an employee profile.')
        return redirect('attendance_today')

    shift = employee.shift or Shift.objects.filter(is_active=True).first()
    if not shift:
        messages.error(request, 'No active shift is available for this employee.')
        return redirect('attendance_today')

    now = timezone.now()
    attendance_date = get_attendance_date_for_shift(shift, now)
    open_attendance = Attendance.objects.filter(
        employee=employee,
        check_out__isnull=True,
        check_in__date__gte=attendance_date - timedelta(days=1),
    ).exists()
    if open_attendance:
        messages.error(request, 'Check out of your previous attendance record before checking in again.')
        return redirect('attendance_today')

    if Attendance.objects.filter(employee=employee, date=attendance_date).exists():
        messages.error(request, 'Employee has already checked in today.')
        return redirect('attendance_today')

    device_id = request.POST.get('device_id', '').strip()
    verification_method = 'Manual'
    verification_device_id = ''

    if employee.biometric_device_type in {'Mobile Phone', 'Fingerprint Scanner', 'RFID Reader'}:
        is_valid, verification_method, error_message = get_biometric_verification(employee, device_id)
        if not is_valid:
            messages.error(request, error_message)
            return redirect('attendance_today')
        verification_device_id = device_id

    status, late_minutes = shift.calculate_checkin_status(now)

    attendance_record = Attendance.objects.create(
        employee=employee,
        date=attendance_date,
        check_in=now,
        status=status,
        verification_method=verification_method,
        verification_device_id=verification_device_id,
        late_minutes=late_minutes,
    )
    create_audit_log(
        request.user,
        'Checked in',
        'Attendance',
        attendance_record.pk,
        f'{employee} checked in using {verification_method}.',
    )
    messages.success(request, f'Checked in successfully. Status: {status}.')
    return redirect('attendance_today')


@login_required(login_url='login')
@require_POST
def attendance_check_out(request):
    employee = getattr(request.user, 'employee_profile', None)
    if not employee:
        messages.error(request, 'This account is not linked to an employee profile.')
        return redirect('attendance_today')

    today = timezone.localdate()
    attendance_record = Attendance.objects.filter(
        employee=employee,
        check_out__isnull=True,
        check_in__date__gte=today - timedelta(days=1),
    ).order_by('-check_in').first()
    if not attendance_record:
        messages.error(request, 'Cannot check out before checking in.')
        return redirect('attendance_today')

    if attendance_record.check_out:
        messages.error(request, 'This attendance record has already been checked out.')
        return redirect('attendance_today')

    device_id = request.POST.get('device_id', '').strip()
    if employee.biometric_device_type in {'Mobile Phone', 'Fingerprint Scanner', 'RFID Reader'}:
        is_valid, verification_method, error_message = get_biometric_verification(employee, device_id)
        if not is_valid:
            messages.error(request, error_message)
            return redirect('attendance_today')
        attendance_record.verification_method = verification_method
        attendance_record.verification_device_id = device_id

    shift = employee.shift or Shift.objects.filter(is_active=True).first()
    check_out_time = timezone.now()
    total_hours, overtime_hours = shift.calculate_work_duration(attendance_record.check_in, check_out_time)

    attendance_record.check_out = check_out_time
    attendance_record.total_work_hours = total_hours
    attendance_record.overtime_hours = overtime_hours
    attendance_record.save(update_fields=['check_out', 'total_work_hours', 'overtime_hours', 'verification_method', 'verification_device_id', 'updated_at'])
    create_audit_log(
        request.user,
        'Checked out',
        'Attendance',
        attendance_record.pk,
        f'{employee} checked out using {attendance_record.verification_method or "Manual"}.',
    )
    messages.success(request, 'Checked out successfully.')
    return redirect('attendance_today')
