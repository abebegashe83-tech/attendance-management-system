from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0005_holiday'),
    ]

    operations = [
        migrations.CreateModel(
            name='OvertimeRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('hours', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('reason', models.TextField()),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Pending', max_length=20)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_overtime_requests', to='auth.user')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='overtime_requests', to='attendance.employee')),
            ],
            options={
                'ordering': ['-date', '-created_at'],
            },
        ),
    ]
