from rest_framework import serializers
from .models import CustomUser
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.models import update_last_login


class LoginSerializer(serializers.ModelSerializer):
    password = serializers.CharField(max_length=255, write_only=True)
    email = serializers.EmailField(max_length=255)

    def get_tokens(self, obj):
        user = CustomUser.objects.get(email=obj['email'])

        return {
            'refresh':user.tokens()['refresh'],
            'access':user.tokens()['access']
        }

    class Meta:
        model = CustomUser
        fields = ['password', 'email', 'tokens']           

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        user = authenticate(email=email, password=password)

        if not user:
            raise AuthenticationFailed("Invalid credentials, try again!")
        
        if not user.is_active:
            raise AuthenticationFailed("Account disabled!")
        
        update_last_login(None, user)
        
        return {
            'email':user.email,
            'tokens':user.tokens,
            'user':user,
        }  