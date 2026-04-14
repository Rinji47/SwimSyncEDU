from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

# Custom account manager
class UserManager(BaseUserManager):
    def create_user(self, username, email, password=None, role='user', **extra_fields):
        if not email:
            raise ValueError('Users must have an email')
        if not username:
            raise ValueError('Users must have a username')
        if not extra_fields.get('full_name'):
            raise ValueError('Users must have a full name')
        if not extra_fields.get('gender'):
            raise ValueError('Users must have a gender')
        if not extra_fields.get('date_of_birth'):
            raise ValueError('Users must have a date of birth')

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, email, password=None, **extra_fields):
        user = self.create_user(username, email, password, role='admin', **extra_fields)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

class User(AbstractBaseUser):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('trainer', 'Trainer'),
        ('admin', 'Admin'),
    )
    
    user_id = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=255, unique=True)
    username = models.CharField(max_length=50, unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    objects = UserManager()
    
    #Optional field for all the users
    full_name = models.CharField(max_length=100)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    gender = models.CharField(max_length=10)
    date_of_birth = models.DateField()

    #Trainer-specific fields
    experience_years = models.IntegerField(blank=True, null=True)
    specialization = models.CharField(max_length=100, blank=True, null=True)
    digital_signature = models.ImageField(upload_to='signatures/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']


    def has_perm(self, perm, obj=None):
        return self.is_superuser
    
    def has_module_perms(self, app_label):
        return self.is_superuser

    def __str__(self):
        return f'{self.username} - {self.role}'
    
    def save(self, *args, **kwargs):
        if self.profile_picture and hasattr(self.profile_picture, "content_type"):
            validate_image(self.profile_picture)
            self.profile_picture = compress_image(self.profile_picture)

        if self.digital_signature and hasattr(self.digital_signature, "content_type"):
            validate_image(self.digital_signature)
            self.digital_signature = compress_image(self.digital_signature)

        super().save(*args, **kwargs)
    

def compress_image(image_field):
    img = Image.open(image_field)
    img_io = BytesIO()
    image_format = img.format

    if image_format == 'JPEG':
        img.save(img_io, format='JPEG', quality=70, optimize=True)
    elif image_format == 'PNG':
        img.save(img_io, format='PNG', optimize=True)
    else:
        return image_field
    
    new_image = ContentFile(img_io.getvalue(), name=image_field.name)
    return new_image

def validate_image(image):
    if image:
        if image.size > 2 * 1024 * 1024:
            raise ValidationError("Image file too large ( > 2MB )")
        if not image.content_type in ['image/jpeg', 'image/png']:
            raise ValidationError("Unsupported file type. Only JPEG and PNG are allowed.")