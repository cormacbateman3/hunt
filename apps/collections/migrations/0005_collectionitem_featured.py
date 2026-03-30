from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('collections', '0004_collectionitem_colors_collectionitem_shape_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='collectionitem',
            name='featured',
            field=models.BooleanField(
                default=False,
                help_text='Pin to the top of your public profile (max 6)',
            ),
        ),
    ]
