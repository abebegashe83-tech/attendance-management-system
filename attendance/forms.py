from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Department, Employee, Holiday, LeaveRequest, OvertimeRequest, Shift


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'given-name'}),
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'family-name'}),
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'username'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if self._meta.model.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email address already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.is_active = False
        if commit:
            user.save()
            self.save_m2m()
        return user


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description', 'manager', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'manager': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ['name', 'start_time', 'end_time', 'grace_period_minutes', 'working_hours', 'is_overnight', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'grace_period_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'working_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25'}),
            'is_overnight': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            'employee_id',
            'first_name',
            'middle_name',
            'last_name',
            'gender',
            'date_of_birth',
            'phone',
            'email',
            'address',
            'department',
            'position',
            'hire_date',
            'employment_status',
            'shift',
            'biometric_id',
            'biometric_device',
            'biometric_device_type',
            'mobile_device_id',
            'biometric_status',
            'biometric_notes',
            'profile_photo',
            'user',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hire_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'employment_status': forms.Select(attrs={'class': 'form-select'}),
            'shift': forms.Select(attrs={'class': 'form-select'}),
            'biometric_id': forms.TextInput(attrs={'class': 'form-control'}),
            'biometric_device': forms.TextInput(attrs={'class': 'form-control'}),
            'biometric_device_type': forms.Select(attrs={'class': 'form-select'}),
            'mobile_device_id': forms.TextInput(attrs={'class': 'form-control'}),
            'biometric_status': forms.Select(attrs={'class': 'form-select'}),
            'biometric_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'profile_photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'user': forms.Select(attrs={'class': 'form-select'}),
        }


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['employee', 'leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee:
            self.fields['employee'].required = False
            self.fields['employee'].widget = forms.HiddenInput()
            self.fields['employee'].initial = employee
        else:
            self.fields['employee'].queryset = Employee.objects.order_by('first_name', 'last_name')

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'The end date cannot be before the start date.')
        return cleaned_data


class HolidayForm(forms.ModelForm):
    class Meta:
        model = Holiday
        fields = ['name', 'holiday_date', 'description', 'is_recurring', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'holiday_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_recurring': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class OvertimeRequestForm(forms.ModelForm):
    class Meta:
        model = OvertimeRequest
        fields = ['employee', 'date', 'hours', 'reason']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25', 'min': '0.25'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee:
            self.fields['employee'].required = False
            self.fields['employee'].widget = forms.HiddenInput()
            self.fields['employee'].initial = employee
        else:
            self.fields['employee'].queryset = Employee.objects.order_by('first_name', 'last_name')

    def clean_hours(self):
        hours = self.cleaned_data['hours']
        if hours <= 0:
            raise forms.ValidationError('Overtime hours must be greater than zero.')
        return hours
