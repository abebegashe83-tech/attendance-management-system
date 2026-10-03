from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0003_employee_biometric_device_type_employee_mobile_device_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='verification_device_id',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='attendance',
            name='verification_method',
            field=models.CharField(choices=[('Manual', 'Manual'), ('Mobile Phone', 'Mobile Phone'), ('Fingerprint Scanner', 'Fingerprint Scanner'), ('RFID Reader', 'RFID Reader')], default='Manual', max_length=30),
        ),
    ]
