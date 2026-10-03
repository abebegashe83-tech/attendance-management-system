from django.contrib.auth.models import Group


REQUEST_REVIEWER_ROLES = ('Super Administrator', 'HR Administrator', 'HR Staff')
REPORT_VIEWER_ROLES = ('Super Administrator', 'HR Administrator', 'HR Staff')


def ensure_default_groups():
    groups = [
        'Super Administrator',
        'HR Administrator',
        'HR Staff',
        'Department Manager',
        'IT Administrator',
        'Employee',
    ]
    created = []
    for group_name in groups:
        group, was_created = Group.objects.get_or_create(name=group_name)
        if was_created:
            created.append(group_name)
    return created


def user_has_role(user, role_name):
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=role_name).exists()


def user_can_review_all_requests(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or any(user_has_role(user, role) for role in REQUEST_REVIEWER_ROLES)


def user_can_review_request(user, employee):
    if user_can_review_all_requests(user):
        return True
    if not employee or not employee.department_id or not user_has_role(user, 'Department Manager'):
        return False
    return employee.department.manager_id == user.pk


def user_can_view_reports(user):
    return user_can_review_all_requests(user) or user_has_role(user, 'Department Manager')
