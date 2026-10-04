from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import OCRISUser


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid username or password.')
        if not user.is_active:
            raise serializers.ValidationError('Account is disabled.')
        data['user'] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = OCRISUser
        fields = [
            'id', 'username', 'full_name', 'email', 'role', 'employee_id',
            'assigned_grade', 'assigned_section', 'is_active', 'last_login',
        ]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = OCRISUser
        fields = [
            'username', 'password', 'first_name', 'last_name', 'email', 'role',
            'employee_id', 'assigned_grade', 'assigned_section',
        ]

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = OCRISUser(**validated_data)
        user.set_password(password)
        user.save()
        return user


class CorrectionSerializer(serializers.Serializer):
    field = serializers.CharField()
    corrected_val = serializers.CharField(allow_blank=True)


class ValidationSubmitSerializer(serializers.Serializer):
    scan_id = serializers.CharField()
    pupil_name = serializers.CharField()
    lrn = serializers.CharField(allow_blank=True, required=False)
    grade_level = serializers.CharField()
    section = serializers.CharField()
    school_year = serializers.CharField()
    corrections = CorrectionSerializer(many=True, required=False)
    confirmed = serializers.BooleanField()
