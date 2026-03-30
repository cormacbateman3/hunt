from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trades', '0003_tradeshipment_carrier_tradeshipment_delivered_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tradeshipment',
            name='local_pickup',
            field=models.BooleanField(
                default=False,
                help_text='This side of the trade will be handled by local pickup',
            ),
        ),
    ]
