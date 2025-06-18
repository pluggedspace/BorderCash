

from django.db import migrations, models
import uuid
import random
import string

def generate_unique_referral_code():
    """Generate 10-character alphanumeric code"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(10))

def populate_referral_codes(apps, schema_editor):
    User = apps.get_model('app', 'User')
    for user in User.objects.all().iterator(chunk_size=1000):
        while True:
            new_code = generate_unique_referral_code()
            if not User.objects.filter(referral_code=new_code).exists():
                user.referral_code = new_code
                user.save(update_fields=['referral_code'])
                break

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0017_emaillog_request_id'),
    ]

    operations = [
        # Step 1: Add field as nullable first
        migrations.AddField(
            model_name='user',
            name='referral_code',
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
        
        # Step 2: Populate all records with unique codes
        migrations.RunPython(
            populate_referral_codes,
            reverse_code=migrations.RunPython.noop
        ),
        
        # Step 3: Alter to be non-nullable and unique
        migrations.AlterField(
            model_name='user',
            name='referral_code',
            field=models.CharField(max_length=20, unique=True, blank=False),
        ),
    ]