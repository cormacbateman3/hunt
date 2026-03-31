import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('listings', '0008_listingquestion_moderation_state'),
        ('trades', '0004_tradeshipment_local_pickup'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Conversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('conversation_type', models.CharField(choices=[('auction', 'Auction'), ('buy_now', 'Buy Now'), ('trade', 'Trade'), ('general', 'General')], max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_message_at', models.DateTimeField(blank=True, null=True)),
                ('is_closed', models.BooleanField(default=False)),
                ('listing', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conversations', to='listings.listing')),
                ('trade_offer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conversations', to='trades.tradeoffer')),
                ('user_a', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversations_as_a', to=settings.AUTH_USER_MODEL)),
                ('user_b', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversations_as_b', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversations_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Conversation',
                'verbose_name_plural': 'Conversations',
                'ordering': ['-last_message_at', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('moderation_state', models.CharField(choices=[('ok', 'OK'), ('flagged', 'Flagged'), ('hidden', 'Hidden')], default='ok', max_length=10)),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='messaging.conversation')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages_sent', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Message',
                'verbose_name_plural': 'Messages',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='MessageRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_read_at', models.DateTimeField()),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='read_records', to='messaging.conversation')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_read_records', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Message Read',
                'verbose_name_plural': 'Message Reads',
            },
        ),
        migrations.CreateModel(
            name='Block',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('blocker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocks_placed', to=settings.AUTH_USER_MODEL)),
                ('blocked', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocks_received', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Block',
                'verbose_name_plural': 'Blocks',
            },
        ),
        migrations.CreateModel(
            name='MessageReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(choices=[('scam', 'Scam'), ('harassment', 'Harassment'), ('spam', 'Spam'), ('other', 'Other')], max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('open', 'Open'), ('reviewing', 'Reviewing'), ('resolved', 'Resolved'), ('dismissed', 'Dismissed')], default='open', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_reports_filed', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='message_reports_resolved', to=settings.AUTH_USER_MODEL)),
                ('message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='messaging.message')),
                ('conversation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='messaging.conversation')),
            ],
            options={
                'verbose_name': 'Message Report',
                'verbose_name_plural': 'Message Reports',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='conversation',
            constraint=models.UniqueConstraint(
                condition=models.Q(listing__isnull=False),
                fields=['listing', 'user_a', 'user_b', 'conversation_type'],
                name='unique_listing_conversation',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='messageread',
            unique_together={('conversation', 'user')},
        ),
        migrations.AlterUniqueTogether(
            name='block',
            unique_together={('blocker', 'blocked')},
        ),
    ]
