from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appname", "0007_add_gn_coachclass"),
    ]

    operations = [
        migrations.AlterField(
            model_name="passengerticket",
            name="status",
            field=models.CharField(
                choices=[
                    ("ACTIVE", "Active"),
                    ("DEPARTED", "Departed"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="ACTIVE",
                max_length=10,
            ),
        ),
    ]
