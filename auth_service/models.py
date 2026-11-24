import uuid

from django.db import models


class User(models.Model):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "STUDENT"
        INSTRUCTOR = "INSTRUCTOR", "INSTRUCTOR"
        ADMIN = "ADMIN", "ADMIN"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_code = models.CharField(max_length=32, unique=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"


class StudentProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, primary_key=True, related_name="student_profile"
    )
    student_id = models.CharField(max_length=64, unique=True)
    firstname = models.CharField(max_length=120)
    lastname = models.CharField(max_length=120)
    program = models.CharField(max_length=120, blank=True, null=True)
    year_level = models.IntegerField(blank=True, null=True)
    ntc_email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "student_profiles"


class InstructorProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="instructor_profile",
    )
    firstname = models.CharField(max_length=120)
    lastname = models.CharField(max_length=120)
    ntc_email = models.EmailField(unique=True)
    subjects = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "instructor_profiles"


class AdminProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, primary_key=True, related_name="admin_profile"
    )
    firstname = models.CharField(max_length=120)
    lastname = models.CharField(max_length=120)
    ntc_email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_profiles"


class RefreshToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="refresh_tokens"
    )
    token_hash = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "refresh_tokens"
