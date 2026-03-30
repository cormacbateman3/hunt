import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0006_listing_colors_listing_is_statewide_listing_shape_and_more'),
    ]

    operations = [
        # 4a: Scheduled go-live
        migrations.AddField(
            model_name='listing',
            name='scheduled_at',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text='Schedule when this listing goes live (leave blank to publish immediately)',
            ),
        ),
        # 4b: Auto-relist
        migrations.AddField(
            model_name='listing',
            name='auto_relist',
            field=models.BooleanField(
                default=True,
                help_text='Automatically relist this auction if it ends without a winner (up to 3 times)',
            ),
        ),
        migrations.AddField(
            model_name='listing',
            name='relist_count',
            field=models.IntegerField(default=0, help_text='How many times this listing has been relisted'),
        ),
        migrations.AddField(
            model_name='listing',
            name='original_listing',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='relisted_copies',
                to='listings.listing',
                help_text='Original listing if this is a relist',
            ),
        ),
        # 4c: Local pickup
        migrations.AddField(
            model_name='listing',
            name='local_pickup_available',
            field=models.BooleanField(
                default=False,
                help_text='Offer local pickup as an alternative to shipping',
            ),
        ),
        migrations.AddField(
            model_name='listing',
            name='local_pickup_location',
            field=models.CharField(
                blank=True, max_length=100,
                help_text="City or region where pickup is available (e.g. 'Lancaster, PA')",
            ),
        ),
        # 4a: Add 'scheduled' to STATUS_CHOICES (data-only change, no schema change needed)
        migrations.AlterField(
            model_name='listing',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('active', 'Active'),
                    ('scheduled', 'Scheduled'),
                    ('closed', 'Closed'),
                    ('sold', 'Sold'),
                    ('expired', 'Expired'),
                    ('cancelled', 'Cancelled'),
                ],
                default='active',
                max_length=20,
            ),
        ),
    ]
