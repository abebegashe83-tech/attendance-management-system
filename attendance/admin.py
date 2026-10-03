from django.contrib import admin

from .models import Attendance, AuditLog, Department, Employee, Holiday, LeaveRequest, OvertimeRequest, Shift


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'manager', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    ordering = ('name',)


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'end_time', 'grace_period_minutes', 'is_active')
    list_filter = ('is_active', 'is_overnight')
    search_fields = ('name',)
    ordering = ('start_time',)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'first_name', 'last_name', 'department', 'position', 'employment_status')
    list_filter = ('employment_status', 'department', 'gender')
    search_fields = ('employee_id', 'first_name', 'last_name', 'email', 'phone')
    ordering = ('last_name', 'first_name')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'check_in', 'check_out', 'status', 'late_minutes', 'overtime_hours')
    list_filter = ('status', 'date', 'employee__department')
    search_fields = ('employee__employee_id', 'employee__first_name', 'employee__last_name', 'remarks')
    ordering = ('-date',)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'status', 'approved_by')
    list_filter = ('status', 'leave_type')
    search_fields = ('employee__first_name', 'employee__last_name', 'reason')
    ordering = ('-created_at',)


@admin.register(OvertimeRequest)
class OvertimeRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'hours', 'status', 'approved_by')
    list_filter = ('status', 'date')
    search_fields = ('employee__first_name', 'employee__last_name', 'reason')
    ordering = ('-date',)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'holiday_date', 'is_recurring', 'is_active')
    list_filter = ('is_recurring', 'is_active')
    search_fields = ('name', 'description')
    ordering = ('holiday_date',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'model_name', 'actor', 'created_at')
    list_filter = ('model_name', 'action', 'created_at')
    search_fields = ('action', 'details', 'model_name')
    ordering = ('-created_at',)
