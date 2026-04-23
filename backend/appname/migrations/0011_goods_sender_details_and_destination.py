from django.db import migrations, models


def backfill_sender_fields(apps, schema_editor):
    GoodsShipment = apps.get_model('appname', 'GoodsShipment')
    for shipment in GoodsShipment.objects.select_related('sender').all():
        if shipment.sender_id and shipment.sender:
            full_name = f"{(shipment.sender.first_name or '').strip()} {(shipment.sender.last_name or '').strip()}".strip()
            shipment.sender_name = full_name or shipment.sender.fullname or shipment.sender.email
            shipment.sender_email = shipment.sender.email
        else:
            shipment.sender_name = shipment.sender_name or 'Unknown Sender'
            shipment.sender_email = shipment.sender_email or 'unknown@example.com'

        shipment.destination = shipment.destination or 'Unknown'
        shipment.save(update_fields=['sender_name', 'sender_email', 'destination'])


class Migration(migrations.Migration):

    dependencies = [
        ('appname', '0010_passengerticket_booking_source'),
    ]

    operations = [
        migrations.AlterField(
            model_name='goodsshipment',
            name='sender',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='goods_shipments', to='appname.user'),
        ),
        migrations.AddField(
            model_name='goodsshipment',
            name='sender_name',
            field=models.CharField(default='Unknown Sender', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='goodsshipment',
            name='sender_email',
            field=models.EmailField(default='unknown@example.com', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='goodsshipment',
            name='destination',
            field=models.CharField(default='Unknown', max_length=100),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_sender_fields, migrations.RunPython.noop),
    ]
