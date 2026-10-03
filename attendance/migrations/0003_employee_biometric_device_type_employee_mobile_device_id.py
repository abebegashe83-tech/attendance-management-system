from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0002_employee_biometric_device_employee_biometric_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='biometric_device_type',
            field=models.CharField(choices=[('Mobile Phone', 'Mobile Phone'), ('Fingerprint Scanner', 'Fingerprint Scanner'), ('RFID Reader', 'RFID Reader'), ('Other', 'Other')], default='Mobile Phone', max_length=30),
        ),
        migrations.AddField(
            model_name='employee',
            name='mobile_device_id',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
    ]
