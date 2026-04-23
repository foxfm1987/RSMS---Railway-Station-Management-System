from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appname", "0006_alter_trainschedule_unique_together"),
    ]

    operations = [
        migrations.AlterField(
            model_name="passengerticket",
            name="coach_class",
            field=models.CharField(
                choices=[
                    ("GN", "General"),
                    ("1A", "1A"),
                    ("2A", "2A"),
                    ("3A", "3A"),
                    ("SL", "SL"),
                    ("CC", "CC"),
                    ("2S", "2S"),
                    ("FC", "FC"),
                ],
                default="SL",
                max_length=3,
            ),
        ),
    ]
