import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("control", "0004_tenantdomain_verification_metadata"),
        ("identity", "0005_rename_password_reset_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="securitysession",
            name="tenant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="security_sessions",
                to="control.tenant",
            ),
        ),
    ]
