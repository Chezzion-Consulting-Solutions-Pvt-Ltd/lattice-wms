# Generated for Lattice secure core.
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="WarehouseProbeObject",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("external_reference", models.CharField(blank=True, max_length=120)),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="warehouse.warehouse")),
            ],
        ),
    ]
