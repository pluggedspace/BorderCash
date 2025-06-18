from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0020_user_is_verified'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='email_verification_token',
            field=models.CharField(max_length=64, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='verification_token_expires',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]