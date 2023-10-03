# Generated by Django 3.2.13 on 2023-07-26 17:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eox_nelp', '0005_paymentnotification'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentnotification',
            name='cdtrans_card_last_4_digits',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='paymentnotification',
            name='internal_notes',
            field=models.TextField(blank=True, max_length=2000, null=True),
        ),
    ]
