from django.shortcuts import render, redirect
from rest_framework.views import APIView
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
import urllib.parse 
import requests
from django_accounts.models import CustomUser
from rest_framework_simplejwt.tokens import RefreshToken
from aps_api.models import AutodeskUser
from datetime import timedelta
from django.utils import timezone



APS_AUTH_URL = "https://developer.api.autodesk.com/authentication/v2/authorize"
APS_TOKEN_URL = "https://developer.api.autodesk.com/authentication/v2/token"
APS_USERINFO_URL = "https://api.userprofile.autodesk.com/userinfo"


# class AutodeskLoginView(APIView):
#     authentication_classes = []
#     permission_classes = []

#     def get(self, request):
#         scopes = "data:read data:write account:read viewables:read bucket:read"

#         auth_url = (
#             f"{APS_AUTH_URL}"
#             f"?response_type=code"
#             f"&client_id={settings.APS_CLIENT_ID}"
#             f"&redirect_uri={settings.APS_REDIRECT_URI}"
#             f"&scope={scopes}"
#         )

#         return redirect(auth_url)
class AutodeskLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):

        scopes = [
            "data:read",
            "data:write",
            "account:read",
            "viewables:read",
            "bucket:read"
        ]

        scope_str = urllib.parse.quote(" ".join(scopes))

        auth_url = (
            f"{APS_AUTH_URL}"
            f"?response_type=code"
            f"&client_id={settings.APS_CLIENT_ID}"
            f"&redirect_uri={settings.APS_REDIRECT_URI}"
            f"&scope={scope_str}"
        )

        return redirect(auth_url)




class AutodeskCallbackView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        code = request.GET.get("code")

        if not code:
            return Response(
                {"error":"Authorization Code Missing"},
                status=status.HTTP_400_BAD_REQUEST
            )
        

        payload = {
            "client_id":settings.APS_CLIENT_ID,
            "client_secret":settings.APS_CLIENT_SECRET,
            "grant_type":"authorization_code",
            "code":code,
            "redirect_uri":settings.APS_REDIRECT_URI
        }

        headers = {
            "Content-Type":"application/x-www-form-urlencoded"
        }


        token_response = requests.post(
            APS_TOKEN_URL, 
            data=payload,
            headers=headers
        )

        if token_response.status_code != 200:
            return Response(
                token_response.json(),
                status=status.HTTP_400_BAD_REQUEST
            ) 
        
        aps_tokens = token_response.json()

        aps_access_token = aps_tokens["access_token"]
        aps_refresh_token = aps_tokens["refresh_token"]

        userinfo_response = requests.get(
            APS_USERINFO_URL,
            headers={
                "Authorization":f"Bearer {aps_access_token}"
            }
        )

        if userinfo_response.status_code != 200:
            return Response(
                {"error":"Failed to fetch autodesk profile"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        profile = userinfo_response.json()

        email = profile.get("email")
        name = profile.get("name", "")

        if not email:
            return Response(
                {"error":"Email Not Available"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user, created = CustomUser.objects.get_or_create(
            email=email,
            defaults={
                "email":email,
                "first_name":name
            }
        )


        AutodeskUser.objects.update_or_create(
            user=user,
            defaults={
                "autodesk_user_id":profile["sub"],
                "email":profile["email"],
                "name":profile["name"],               
                "access_token":aps_access_token,
                "refresh_token":aps_refresh_token,
                "expires_at":timezone.now() + timedelta(seconds=aps_tokens["expires_in"])
            }
        )

        refresh = RefreshToken.for_user(user)

        refresh["autodesk_connected"] = True

        # access_token = str(refresh.access_token)
        # refresh_token = str(refresh)

        return Response(
            {
                "aps_access_token":aps_access_token,
            }
        )