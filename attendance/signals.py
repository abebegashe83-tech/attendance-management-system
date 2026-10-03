from django.apps import apps
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def create_default_groups(sender, **kwargs):
    if sender.name != 'attendance':
        return

    from .permissions import ensure_default_groups

    ensure_default_groups()
