from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0006_overtimerequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='base_salary',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=12),
        ),
        migrations.AddField(
            model_name='employee',
            name='hourly_rate',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.CreateModel(
            name='PayrollRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pay_period', models.CharField(max_length=20)),
                ('base_salary', models.DecimalField(decimal_places=2, default=0.0, max_digits=12)),
                ('overtime_hours', models.DecimalField(decimal_places=2, default=0.0, max_digits=8)),
                ('overtime_pay', models.DecimalField(decimal_places=2, default=0.0, max_digits=12)),
                ('bonus', models.DecimalField(decimal_places=2, default=0.0, max_digits=12)),
                ('deductions', models.DecimalField(decimal_places=2, default=0.0, max_digits=12)),
                ('gross_pay', models.DecimalField(decimal_places=2, default=0.0, max_digits=12)),
                ('net_pay', models.DecimalField(decimal_places=2, default=0.0, max_digits=12)),
                ('status', models.CharField(choices=[('Draft', 'Draft'), ('Approved', 'Approved'), ('Paid', 'Paid')], default='Draft', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payroll_records', to='attendance.employee')),
            ],
            options={
                'ordering': ['-pay_period', '-created_at'],
                'unique_together': {('employee', 'pay_period')},
            },
        ),
    ]
