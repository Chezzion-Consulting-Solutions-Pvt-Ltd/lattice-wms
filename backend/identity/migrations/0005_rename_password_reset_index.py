from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0004_passwordresettoken"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="passwordresettoken",
            new_name="identity_pa_user_id_811dd1_idx",
            old_name="identity_pa_user_id_47fa85_idx",
        ),
    ]
