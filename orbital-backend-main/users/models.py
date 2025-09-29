from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os
import uuid

protected_storage = FileSystemStorage(
    location=os.path.join(settings.BASE_DIR, 'media-protected'))


def profile_pic_upload_to(instance, filename):
    ext = filename.split('.')[-1]

    filename = f"{instance.profile_pic_uuid}.{ext}"
    return os.path.join('profile_pics', filename)


def uen_doc_upload_to(instance, filename):
    return os.path.join('uen_docs', filename)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    profile_pic_uuid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True)
    profile_pic = models.ImageField(
        upload_to=profile_pic_upload_to,
        blank=True,
        null=True
    )

    class Role(models.TextChoices):
        REVIEWER = 'reviewer', 'Reviewer'
        VENDOR = 'vendor', 'Vendor'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.REVIEWER,
    )

    verified = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        try:
            old = User.objects.get(pk=self.pk)
            if old.profile_pic and self.profile_pic and old.profile_pic != self.profile_pic:
                old_pic_path = str(old.profile_pic)
                if not old_pic_path.endswith('default.jpg') and not 'default.jpg' in old_pic_path:
                    if os.path.isfile(old.profile_pic.path):
                        os.remove(old.profile_pic.path)
        except User.DoesNotExist:
            pass
        super().save(*args, **kwargs)


class Vendor(models.Model):
    vendor_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='vendor_profile')
    company_name = models.CharField(max_length=255, blank=True, null=False)
    vendor_uen = models.CharField(max_length=255, blank=True, null=False)
    vendor_uen_doc = models.FileField(
        upload_to=uen_doc_upload_to,
        storage=protected_storage,
        blank=True,
        null=True
    )
    vendor_status = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.user.role = User.Role.VENDOR
            self.user.save()
        super().save(*args, **kwargs)


class Reviewer(models.Model):
    class Level(models.TextChoices):
        BRONZE = 'bronze', 'Bronze'
        SILVER = 'silver', 'Silver'
        GOLD = 'gold', 'Gold'
        PLATINUM = 'platinum', 'Platinum'

    reviewer_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='reviewer_profile')
    reviewer_level = models.CharField(
        max_length=50, choices=Level.choices, default=Level.BRONZE
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            self.user.role = User.Role.REVIEWER
            self.user.save()
        super().save(*args, **kwargs)
