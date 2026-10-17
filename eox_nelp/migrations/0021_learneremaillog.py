"""Adds the log that makes learner e-mails go out once (no foreign key on purpose)."""
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eox_nelp', '0020_mt_delivery_null_response_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='LearnerEmailLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.IntegerField()),
                ('course_id', models.CharField(max_length=255)),
                ('kind', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.AddConstraint(
            model_name='learneremaillog',
            constraint=models.UniqueConstraint(fields=('user_id', 'course_id', 'kind'), name='learner_email_log_once'),
        ),
    ]
