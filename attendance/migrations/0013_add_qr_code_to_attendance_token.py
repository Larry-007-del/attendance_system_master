from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0012_alter_attendance_options_alter_course_students_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancetoken',
            name='qr_code',
            field=models.ImageField(null=True, blank=True, upload_to='qr_codes/'),
        ),
    ]