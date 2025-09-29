from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import LoginSerializer
from rest_framework.validators import UniqueValidator
from rest_framework import serializers
from .models import User, Vendor, Reviewer


class ReviewerRegisterSerializer(RegisterSerializer):
    username = serializers.CharField(required=True)
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    profile_pic = serializers.ImageField(
        required=False, allow_null=True, use_url=True)

    def validate_role(self, value):
        if value not in [User.Role.REVIEWER, User.Role.VENDOR]:
            raise serializers.ValidationError(
                "Only reviewers or vendors can register.")
        return value

    def custom_signup(self, request, user):
        user.first_name = self.validated_data.get('first_name', '')
        user.last_name = self.validated_data.get('last_name', '')
        user.role = User.Role.REVIEWER
        profile_pic = self.validated_data.get('profile_pic', None)
        if profile_pic:
            user.profile_pic = profile_pic
        user.save()

        Reviewer.objects.create(user=user)


class VendorRegisterSerializer(RegisterSerializer):
    username = serializers.CharField(required=True)
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    company_name = serializers.CharField(required=True)
    vendor_uen = serializers.CharField(required=True)
    profile_pic = serializers.ImageField(
        required=False, allow_null=True, use_url=True)
    vendor_uen_doc = serializers.FileField(required=False, allow_null=True)

    def custom_signup(self, request, user):
        profile_pic = self.validated_data.get('profile_pic', None)
        if profile_pic:
            user.profile_pic = profile_pic

        user.role = User.Role.VENDOR
        user.save()
        Vendor.objects.create(
            user=user,
            company_name=self.validated_data['company_name'],
            vendor_uen=self.validated_data['vendor_uen'],
            vendor_uen_doc=self.validated_data.get('vendor_uen_doc', None),
        )


class CustomLoginSerializer(LoginSerializer):
    pass


class CustomUserDetailsSerializer(serializers.ModelSerializer):
    profile_pic = serializers.SerializerMethodField()
    reviewer_id = serializers.SerializerMethodField()
    vendor_id = serializers.SerializerMethodField()
    vendor_status = serializers.CharField(
        source='vendor_profile.vendor_status', read_only=True)
    email = serializers.EmailField(
        required=False,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, style={'input_type': 'password'})
    role = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'profile_pic',
                  'role', 'reviewer_id', 'vendor_id', 'password', 'vendor_status']
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
        }

    def get_reviewer_id(self, obj):
        if obj.role == User.Role.REVIEWER:
            # If you have a OneToOneField from Reviewer to User:
            reviewer = getattr(obj, 'reviewer_profile', None)
            if reviewer:
                return reviewer.reviewer_id
        return None

    def get_vendor_id(self, obj):
        if obj.role == User.Role.VENDOR:
            # If you have a OneToOneField from Vendor to User:
            vendor = getattr(obj, 'vendor_profile', None)
            if vendor:
                return vendor.vendor_id
        return None

    def get_profile_pic(self, obj):
        if obj.profile_pic and obj.profile_pic.name:
            return obj.profile_pic.url
        else:
            return '/media/default/default.jpg'

    def update(self, instance, validated_data):
        # Handle profile_pic update
        if 'profile_pic' in self.initial_data:
            instance.profile_pic = self.initial_data['profile_pic']

        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)

        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class CustomVendorSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', required=False)
    email = serializers.EmailField(source='user.email', required=False)
    profile_pic = serializers.SerializerMethodField()
    protected_uen_doc_url = serializers.SerializerMethodField()
    password = serializers.CharField(source='user.password', write_only=True,
                                     required=False, allow_blank=True, style={'input_type': 'password'})

    class Meta:
        model = Vendor
        fields = ['vendor_id', 'username', 'email', 'company_name',
                  'vendor_uen', 'vendor_uen_doc', 'protected_uen_doc_url', 'profile_pic', 'vendor_status', 'password']
        read_only_fields = ['vendor_id', 'vendor_status']

    def get_profile_pic(self, obj):
        if obj.user.profile_pic and obj.user.profile_pic.name:
            return obj.user.profile_pic.url
        else:
            return '/media/default/default.jpg'

    def get_protected_uen_doc_url(self, obj):
        request = self.context.get('request')
        if obj.vendor_uen_doc and request:
            return request.build_absolute_uri(f"/protected/uen_doc/{obj.pk}/")
        return None

    def update(self, instance, validated_data):
        user_updated = False

        # Handle user fields - check both validated_data and initial_data
        if 'profile_pic' in self.initial_data:
            instance.user.profile_pic = self.initial_data['profile_pic']
            user_updated = True
            
        # Handle username from initial_data since it's a nested field
        if 'username' in self.initial_data:
            instance.user.username = self.initial_data['username']
            user_updated = True
            
        # Handle email from initial_data since it's a nested field  
        if 'email' in self.initial_data:
            instance.user.email = self.initial_data['email']
            user_updated = True

        user_data = validated_data.pop('user', {})
        password = user_data.get('password')
        if password:
            instance.user.set_password(password)
            user_updated = True

        if user_updated:
            instance.user.save()

        # Update Vendor fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ResendEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
