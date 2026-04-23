from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appname', '0008_add_departed_ticket_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='passengerticket',
            name='passenger_count',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='passengerticket',
            name='passenger_details',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
