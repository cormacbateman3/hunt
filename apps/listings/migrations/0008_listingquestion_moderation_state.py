from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0007_listing_9_4_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='listingquestion',
            name='moderation_state',
            field=models.CharField(
                choices=[('ok', 'OK'), ('flagged', 'Flagged'), ('hidden', 'Hidden')],
                default='ok',
                help_text='ok = visible; flagged = visible but under review; hidden = removed from public view',
                max_length=10,
            ),
        ),
    ]
