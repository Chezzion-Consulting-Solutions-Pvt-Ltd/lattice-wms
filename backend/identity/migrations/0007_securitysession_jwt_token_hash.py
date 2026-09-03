from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0006_securitysession_tenant"),
    ]

    operations = [
        migrations.AddField(
            model_name="securitysession",
            name="jwt_token_hash",
            field=models.CharField(blank=True, max_length=128, null=True, unique=True),
        ),
    ]
