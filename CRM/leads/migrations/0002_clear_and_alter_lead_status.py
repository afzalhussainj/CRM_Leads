# Generated manually to clear leads data and change status field to ForeignKey

from django.db import migrations, models
import django.db.models.deletion

def clear_leads_data(apps, schema_editor):
    # Clear all leads data since it's not important
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM lead")

def reverse_clear_leads_data(apps, schema_editor):
    # No need to reverse this
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0001_initial'),
        ('common', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(clear_leads_data, reverse_clear_leads_data),
        migrations.AlterField(
            model_name='lead',
            name='status',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, to='common.leadstatus'),
        ),
    ]
