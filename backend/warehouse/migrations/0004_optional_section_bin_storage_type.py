import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("warehouse", "0003_hierarchy_actor_user_ids"),
    ]

    operations = [
        migrations.AlterField(
            model_name="storagesection",
            name="storage_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="sections",
                to="warehouse.storagetype",
            ),
        ),
        migrations.AlterField(
            model_name="bin",
            name="storage_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="bins",
                to="warehouse.storagetype",
            ),
        ),
    ]
