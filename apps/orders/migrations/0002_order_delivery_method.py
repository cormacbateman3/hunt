from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='delivery_method',
            field=models.CharField(
                choices=[('shipping', 'Shipping'), ('local_pickup', 'Local Pickup')],
                default='shipping',
                max_length=20,
            ),
        ),
    ]
