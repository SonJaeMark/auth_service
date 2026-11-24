import json

import jwt
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from auth_service.auth_utils import (
    create_access_token,
    create_refresh_token_value,
    decode_access_token,
    generate_user_code,
    hash_password,
    hash_token,
    split_full_name,
    verify_password,
)

from .models import AdminProfile, InstructorProfile, RefreshToken, StudentProfile, User


def _parse_json(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _get_bearer_user(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return None
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError:
        return None

    user_code = claims.get("sub")
    if not user_code:
        return None
    return User.objects.filter(user_code=user_code, is_active=True).first()


@require_GET
def health_check(request):
    return JsonResponse(
        {
            "status": "UP",
            "service": "auth-service",
            "timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        status=200,
    )


@csrf_exempt
@require_POST
def register(request):
    data = _parse_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    full_name = (data.get("fullName") or "").strip()
    role = (data.get("role") or "STUDENT").strip().upper()

    if not email or not password or not full_name:
        return JsonResponse(
            {"error": "email, password, and fullName are required"}, status=400
        )

    valid_roles = {User.Role.STUDENT, User.Role.INSTRUCTOR, User.Role.ADMIN}
    if role not in valid_roles:
        return JsonResponse({"error": "Invalid role"}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=409)

    firstname, lastname = split_full_name(full_name)

    with transaction.atomic():
        user = User.objects.create(
            user_code=generate_user_code(),
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
        )

        if role == User.Role.STUDENT:
            student_id = (
                data.get("studentId")
                or f"STU-{user.user_code.removeprefix('usr_').upper()}"
            ).strip()
            StudentProfile.objects.create(
                user=user,
                student_id=student_id,
                firstname=firstname,
                lastname=lastname,
                program=data.get("program"),
                year_level=data.get("yearLevel"),
                ntc_email=(data.get("ntcEmail") or email).strip().lower(),
                is_active=True,
            )
        elif role == User.Role.INSTRUCTOR:
            InstructorProfile.objects.create(
                user=user,
                firstname=firstname,
                lastname=lastname,
                ntc_email=(data.get("ntcEmail") or email).strip().lower(),
                subjects=data.get("subjects") or [],
                is_active=True,
            )
        elif role == User.Role.ADMIN:
            AdminProfile.objects.create(
                user=user,
                firstname=firstname,
                lastname=lastname,
                ntc_email=(data.get("ntcEmail") or email).strip().lower(),
            )

    return JsonResponse(
        {
            "userId": user.user_code,
            "email": user.email,
            "role": user.role,
            "createdAt": user.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        status=201,
    )


@csrf_exempt
@require_POST
def login(request):
    data = _parse_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.objects.filter(email=email, is_active=True).first()
    if not user or not verify_password(password, user.password_hash):
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    access_token, expires_in = create_access_token(user)
    raw_refresh, refresh_hash, expires_at = create_refresh_token_value()

    RefreshToken.objects.create(
        user=user,
        token_hash=refresh_hash,
        expires_at=expires_at,
    )

    return JsonResponse(
        {
            "accessToken": access_token,
            "refreshToken": raw_refresh,
            "tokenType": "Bearer",
            "expiresIn": expires_in,
        },
        status=200,
    )


@csrf_exempt
@require_POST
def refresh_token(request):
    data = _parse_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    raw_refresh = (data.get("refreshToken") or "").strip()
    if not raw_refresh:
        return JsonResponse({"error": "refreshToken is required"}, status=400)

    token_record = (
        RefreshToken.objects.select_related("user")
        .filter(
            token_hash=hash_token(raw_refresh),
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
            user__is_active=True,
        )
        .first()
    )
    if not token_record:
        return JsonResponse({"error": "Invalid or expired refresh token"}, status=401)

    access_token, expires_in = create_access_token(token_record.user)
    return JsonResponse(
        {
            "accessToken": access_token,
            "expiresIn": expires_in,
        },
        status=200,
    )


@csrf_exempt
@require_POST
def logout(request):
    user = _get_bearer_user(request)
    if not user:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    raw_refresh = (data.get("refreshToken") or "").strip()
    if raw_refresh:
        RefreshToken.objects.filter(
            user=user,
            token_hash=hash_token(raw_refresh),
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())

    return HttpResponse(status=204)


@require_GET
def me(request):
    user = _get_bearer_user(request)
    if not user:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    return JsonResponse(
        {
            "userId": user.user_code,
            "email": user.email,
            "fullName": user.full_name,
            "role": user.role,
        },
        status=200,
    )
