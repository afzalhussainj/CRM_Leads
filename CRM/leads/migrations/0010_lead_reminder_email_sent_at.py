from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0009_remove_follow_up_status_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="reminder_email_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
