from django.db import migrations, models


def set_booking_source(apps, schema_editor):
    PassengerTicket = apps.get_model('appname', 'PassengerTicket')

    PassengerTicket.objects.filter(user__role='PASSENGER').update(booking_source='PASSENGER_PORTAL')
    PassengerTicket.objects.filter(user__role='TICKET_STAFF').update(booking_source='TICKET_COUNTER')
    PassengerTicket.objects.filter(booking_source='UNKNOWN').update(booking_source='PASSENGER_PORTAL')


class Migration(migrations.Migration):

    dependencies = [
        ('appname', '0009_passengerticket_passenger_count_and_details'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='passengerticket',
                    name='booking_source',
                    field=models.CharField(
                        choices=[
                            ('PASSENGER_PORTAL', 'Passenger Portal'),
                            ('TICKET_COUNTER', 'Ticket Counter'),
                            ('UNKNOWN', 'Unknown'),
                        ],
                        default='UNKNOWN',
                        max_length=20,
                    ),
                ),
            ],
        ),
        migrations.RunPython(set_booking_source, migrations.RunPython.noop),
    ]
