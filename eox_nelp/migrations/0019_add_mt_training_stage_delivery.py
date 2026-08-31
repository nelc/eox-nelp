"""Adds the MT training stage delivery record."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('eox_nelp', '0018_db_rm_experience_user_foreign_key'),
    ]

    operations = [
        migrations.CreateModel(
            name='MTTrainingStageDelivery',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('national_id', models.CharField(help_text='The normalized national ID that was sent to the partner.', max_length=20)),
                ('course_id', models.CharField(help_text='The course the result belongs to.', max_length=255)),
                ('stage_result', models.PositiveSmallIntegerField(help_text='Representation of pass or fail result, 1 for pass, 2 for fail.')),
                ('attempts', models.PositiveIntegerField(default=0, help_text='How many times this result has been sent.')),
                ('last_response_code', models.CharField(blank=True, help_text="The partner's most recent response code.", max_length=16, null=True)),
                ('last_response_message', models.TextField(blank=True, default='', help_text="The partner's most recent response message.")),
                ('acknowledged', models.BooleanField(default=False, help_text='Whether the partner has ever accepted this result.')),
                ('acknowledged_at', models.DateTimeField(blank=True, help_text='When the partner first accepted this result.', null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, help_text='When this result was first sent.')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='When this result was last sent.')),
                ('user', models.ForeignKey(help_text='The account this result belongs to, for reporting only.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mt_training_stage_deliveries', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'MT Training Stage Delivery',
                'verbose_name_plural': 'MT Training Stage Deliveries',
                'unique_together': {('national_id', 'course_id', 'stage_result')},
            },
        ),
        migrations.AddIndex(
            model_name='mttrainingstagedelivery',
            index=models.Index(fields=['acknowledged', 'updated_at'], name='mt_delivery_ack_updated_idx'),
        ),
    ]
