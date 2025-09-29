from rest_framework.permissions import AllowAny
from allauth.account.utils import send_email_confirmation
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, GenericAPIView
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.authtoken.models import Token
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from dj_rest_auth.registration.views import complete_signup, VerifyEmailView
from allauth.account.models import EmailConfirmation, EmailConfirmationHMAC
from dj_rest_auth.app_settings import api_settings
from allauth.account import app_settings as allauth_account_settings
from .serializers import (
    ReviewerRegisterSerializer,
    VendorRegisterSerializer,
    CustomLoginSerializer,
    CustomUserDetailsSerializer,
    CustomVendorSerializer,
    ResendEmailSerializer
)
from dj_rest_auth.utils import jwt_encode
from dj_rest_auth.views import LoginView
from .models import User, Vendor
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
import mimetypes


@api_view(['GET'])
@permission_classes([AllowAny])
def check_username_email(request):
    username = request.GET.get('username')
    email = request.GET.get('email')
    exists = {}

    if username:
        exists['username'] = User.objects.filter(username=username).exists()
    if email:
        exists['email'] = User.objects.filter(email=email).exists()

    return JsonResponse(exists)


class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        # Try to get refresh token from body, else from cookie
        refresh = request.data.get("refresh") or request.COOKIES.get(
            "backend-users-refresh-token")
        if not refresh:
            return Response({"detail": "No refresh token provided."}, status=400)
        serializer = TokenRefreshSerializer(data={"refresh": refresh})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


@method_decorator(sensitive_post_parameters('password1', 'password2'), name='dispatch')
class ReviewerCustomRegisterView(CreateAPIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]
    serializer_class = ReviewerRegisterSerializer
    token_model = Token
    throttle_scope = 'dj_rest_auth'
    role = 'reviewer'

    def perform_create(self, serializer):
        user = serializer.save(self.request)  # This calls custom_signup
        if allauth_account_settings.EMAIL_VERIFICATION != allauth_account_settings.EmailVerificationMethod.MANDATORY:
            if api_settings.USE_JWT:
                self.access_token, self.refresh_token = jwt_encode(user)
            elif self.token_model:
                # Default token creation logic
                token, created = self.token_model.objects.get_or_create(
                    user=user)
        complete_signup(
            self.request, user,
            allauth_account_settings.EMAIL_VERIFICATION,
            None,
        )
        send_email_confirmation(self.request, user)
        return user

    def get_response_data(self, user):
        serializer = CustomUserDetailsSerializer(
            user, context=self.get_serializer_context())
        data = serializer.data
        if api_settings.USE_JWT:
            data['access'] = str(self.access_token)
            data['refresh'] = str(self.refresh_token)
        elif self.token_model:
            data['token'] = user.auth_token.key
        return data

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data['role'] = self.role
        user = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        data = self.get_response_data(user)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

# -------------- Vendor Registration View --------------


@method_decorator(sensitive_post_parameters('password1', 'password2'), name='dispatch')
class VendorCustomRegisterView(CreateAPIView):
    """
    Registers a new vendor user.
    Accepts: username, email, password1, password2, vendor_name, vendor_uen, vendor_uen_doc, profile_pic
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]
    serializer_class = VendorRegisterSerializer
    token_model = Token
    throttle_scope = 'dj_rest_auth'
    role = 'vendor'

    def perform_create(self, serializer):
        user = serializer.save(self.request)  # This calls custom_signup
        if allauth_account_settings.EMAIL_VERIFICATION != allauth_account_settings.EmailVerificationMethod.MANDATORY:
            if api_settings.USE_JWT:
                self.access_token, self.refresh_token = jwt_encode(user)
            elif self.token_model:
                # Default token creation logic
                token, created = self.token_model.objects.get_or_create(
                    user=user)
        complete_signup(
            self.request, user,
            allauth_account_settings.EMAIL_VERIFICATION,
            None,
        )
        send_email_confirmation(self.request, user)
        return user

    def get_response_data(self, user):
        serializer = CustomUserDetailsSerializer(
            user, context=self.get_serializer_context())
        data = serializer.data
        if api_settings.USE_JWT:
            data['access'] = str(self.access_token)
            data['refresh'] = str(self.refresh_token)
        elif self.token_model:
            data['token'] = user.auth_token.key
        return data

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data['role'] = self.role
        user = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        data = self.get_response_data(user)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

# -------------- Custom Login View (for all users) --------------


class CustomLoginView(LoginView):
    serializer_class = CustomLoginSerializer

    def get_response(self):
        user = self.user
        if not user.verified:
            response = Response(
                {'detail': 'Account needs to be verified before login.'},
                status=status.HTTP_403_FORBIDDEN
            )
            # Delete the refresh token cookie if it exists
            response.delete_cookie(
                "backend-users-refresh-token",
                path="/auth/token/refresh/"
            )

            response.delete_cookie(
                "backend-users-access-token",
                path="/auth/token/refresh/"
            )

            # Clear the session data
            self.request.session.flush()
            return response

        # Call the parent to get the default response
        response = super().get_response()
        # Replace user data with your custom serializer output
        if response.data is not None and 'user' in response.data:
            user_data = CustomUserDetailsSerializer(self.user).data
            response.data['user'] = user_data

        refresh = response.data.get("refresh")
        if refresh:
            response.set_cookie(
                "backend-users-refresh-token",
                refresh,
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="Lax",
                path="/auth/token/refresh/"
            )

        return response

# -------------- User Profile Views --------------
# Only for reading user details, not for updating


class UserProfileView(RetrieveUpdateAPIView):
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        user = self.request.user
        if user.role not in [user.Role.VENDOR, user.Role.REVIEWER]:
            raise PermissionError('Not a vendor or reviewer.')
        return user

    def put(self, request, *args, **kwargs):
        return Response({'detail': 'PUT method not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

# -------------- Reviewer Profile Views --------------


class ReviewerProfileView(RetrieveUpdateAPIView):
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        user = self.request.user
        if user.role != user.Role.REVIEWER:
            raise PermissionError('Not a reviewer.')
        return user

    def put(self, request, *args, **kwargs):
        return Response({'detail': 'PUT method not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

# -------------- Vendor Profile Views --------------


class VendorProfileView(RetrieveUpdateAPIView):
    serializer_class = CustomVendorSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        user = request.user
        if user.role != user.Role.VENDOR:
            return Response({'detail': 'Not a vendor.'}, status=403)
        try:
            vendor_profile = user.vendor_profile  # OneToOneField related_name
        except Vendor.DoesNotExist:
            return Response({'detail': 'Vendor profile not found.'}, status=404)
        serializer = CustomVendorSerializer(
            vendor_profile, context={'request': request})
        return Response(serializer.data)

    def get_object(self):
        user = self.request.user
        if user.role != user.Role.VENDOR:
            raise PermissionError('Not a vendor.')
        return user.vendor_profile

    def put(self, request, *args, **kwargs):
        return Response({'detail': 'PUT method not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

# -------------- Protected Vendor Document View --------------


class ProtectedVendorDocView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            if not hasattr(request.user, "vendor_profile"):
                return HttpResponse(status=403)
            vendor = request.user.vendor_profile
            file_handle = vendor.vendor_uen_doc.open()
            # Guess the content type from the file name
            mime_type, _ = mimetypes.guess_type(vendor.vendor_uen_doc.name)
            response = FileResponse(
                file_handle, content_type=mime_type or 'application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{vendor.vendor_uen_doc.name}"'
            return response
        except Vendor.DoesNotExist:
            raise Http404


class CustomVerifyEmailView(VerifyEmailView):
    def get(self, request, key, *args, **kwargs):
        # Try to confirm using HMAC (default allauth method)
        confirmation = EmailConfirmationHMAC.from_key(key)
        if not confirmation:
            # Try to get confirmation from DB as fallback
            try:
                confirmation = EmailConfirmation.objects.get(key=key.lower())
            except EmailConfirmation.DoesNotExist:
                return HttpResponse("Invalid or expired confirmation link.", status=status.HTTP_400_BAD_REQUEST)
        confirmation.confirm(request)
        # Mark the user as verified
        user = confirmation.email_address.user
        user.verified = True
        user.save()

        return HttpResponse("Your email has been confirmed! You can now log in.", status=status.HTTP_200_OK)


class CustomResendEmailView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ResendEmailSerializer

    def post(self, request, *args, **kwargs):
        serializer = ResendEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            if user.verified:
                return Response({"detail": "Email already verified."}, status=status.HTTP_400_BAD_REQUEST)
            # Send the email confirmation using allauth's adapter
            send_email_confirmation(request, user)
            return Response({"detail": "Verification email sent."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"detail": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def custom_logout(request):
    response = Response({"detail": "Logged out."})
    response.delete_cookie("backend-users-refresh-token",
                           path="/auth/token/refresh/")
    return response
