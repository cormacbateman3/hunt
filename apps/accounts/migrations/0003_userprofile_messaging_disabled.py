from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_userprofile_phone_verified_address_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='messaging_disabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='messaging_disabled_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='messaging_disabled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
