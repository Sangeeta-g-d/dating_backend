from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_api', '0015_passwordresettoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='is_blocked',
            field=models.BooleanField(default=False),
        ),
    ]
