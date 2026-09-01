from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("warehouse", "0002_plant_warehouse_address_line_1_and_more"),
    ]

    operations = [
        migrations.AddField("plant", "created_by_user_id", models.UUIDField(blank=True, null=True)),
        migrations.AddField("plant", "updated_by_user_id", models.UUIDField(blank=True, null=True)),
        migrations.AddField("warehouse", "created_by_user_id", models.UUIDField(blank=True, null=True)),
        migrations.AddField("warehouse", "updated_by_user_id", models.UUIDField(blank=True, null=True)),
        migrations.AddField("zone", "created_by_user_id", models.UUIDField(blank=True, null=True)),
        migrations.AddField("zone", "updated_by_user_id", models.UUIDField(blank=True, null=True)),
        migrations.AddField("storagetype", "created_by_user_id", models.UUIDField(blank=True, null=True)),
        migrations.AddField("storagetype", "updated_by_user_id", models.UUIDField(blank=True, null=True)),
        migrations.AddField("storagesection", "created_by_user_id", models.UUIDField(blank=True, null=True)),
        migrations.AddField("storagesection", "updated_by_user_id", models.UUIDField(blank=True, null=True)),
        migrations.AddField("bin", "created_by_user_id", models.UUIDField(blank=True, null=True)),
        migrations.AddField("bin", "updated_by_user_id", models.UUIDField(blank=True, null=True)),
    ]
