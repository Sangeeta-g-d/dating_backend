from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import *
from . models import *
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.core.mail import send_mail
from rest_framework.permissions import IsAuthenticated,AllowAny  
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status, permissions


# user registration View
# Updated UserRegistrationAPIView with detailed debugging
class UserRegistrationAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        print("🔍 DEBUG - Registration request received")
        print(f"🔍 DEBUG - Files in request: {request.FILES}")
        print(f"🔍 DEBUG - Data in request: {request.data}")
        
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            print("🔍 DEBUG - Serializer is valid")
            
            try:
                user = serializer.save()
                print(f"🔍 DEBUG - User saved with ID: {user.id}")

                # Detailed profile photo debugging
                if user.profile_photo:
                    print(f"🔍 DEBUG - Profile photo attributes:")
                    print(f"   - name: {user.profile_photo.name}")
                    print(f"   - url: {user.profile_photo.url}")
                    print(f"   - size: {user.profile_photo.size}")
                    print(f"   - path: {getattr(user.profile_photo, 'path', 'No path attribute')}")
                    
                    # Check S3 existence
                    from django.core.files.storage import default_storage
                    exists = default_storage.exists(user.profile_photo.name)
                    print(f"🔍 DEBUG - File exists in S3: {exists}")
                    
                    if exists:
                        size = default_storage.size(user.profile_photo.name)
                        print(f"🔍 DEBUG - Actual file size in S3: {size} bytes")
                    else:
                        print("❌ DEBUG - FILE WAS NOT UPLOADED TO S3!")
                        print("❌ DEBUG - This is the root cause!")
                        
                else:
                    print("🔍 DEBUG - No profile photo attached to user")

                # Generate tokens and response...
                refresh = RefreshToken.for_user(user)
                response_data = {
                    "status": "200",
                    "message": "User registered successfully",
                    "Response": [
                        {
                            "id": user.id,
                            "full_name": user.full_name,
                            "email": user.email,
                            "phone_number": user.phone_number,
                            "city": user.city,
                            "state": user.state,
                            "country": user.country,
                            "profile_photo": user.profile_photo.url if user.profile_photo else None,
                            "tokens": {
                                "refresh": str(refresh),
                                "access": str(refresh.access_token),
                            },
                        }
                    ]
                }
                return Response(response_data, status=status.HTTP_200_OK)
                
            except Exception as e:
                print(f"❌ DEBUG - Error during user creation: {str(e)}")
                import traceback
                traceback.print_exc()
                return Response({
                    "status": "400", 
                    "message": f"Error: {str(e)}"
                }, status=status.HTTP_400_BAD_REQUEST)

        else:
            print(f"🔍 DEBUG - Serializer errors: {serializer.errors}")
            response_data = {
                "status": "400",
                "message": "Validation errors",
                "Response": serializer.errors
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
# user login API
class UserLoginAPIView(APIView):
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            user = serializer.validated_data["user"]

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            response_data = {
                "status": "200",
                "message": "Login successful",
                "Response": [
                    {
                        "id": user.id,
                        "full_name": user.full_name,
                        "email": user.email,
                        "phone_number": user.phone_number,
                        "city": user.city,
                        "state": user.state,
                        "country": user.country,
                        "profile_photo": user.profile_photo.url if user.profile_photo else None,
                        "tokens": {
                            "refresh": str(refresh),
                            "access": str(refresh.access_token),
                        },
                    }
                ]
            }

            return Response(response_data, status=status.HTTP_200_OK)

        # For errors
        response_data = {
            "status": "400",
            "message": "Invalid credentials",
            "Response": serializer.errors
        }
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)


class SendOTPAPIView(APIView):
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]

            # Check if user exists
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                response_data = {
                    "status": "404",
                    "message": "User not found",
                    "Response": []
                }
                return Response(response_data, status=status.HTTP_404_NOT_FOUND)

            # Generate OTP
            otp = EmailOTP.generate_otp()
            EmailOTP.objects.create(email=email, otp=otp)

            # Send OTP via email
            send_mail(
                subject="Your Login OTP",
                message=f"Your OTP is {otp}. It will expire in 5 minutes.",
                from_email="noreply@example.com",
                recipient_list=[email],
                fail_silently=False,
            )

            response_data = {
                "status": "200",
                "message": "OTP sent successfully",
                "Response": []
            }
            return Response(response_data, status=status.HTTP_200_OK)

        # Validation errors
        response_data = {
            "status": "400",
            "message": "Validation errors",
            "Response": serializer.errors
        }
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
class VerifyOTPAPIView(APIView):
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            otp = serializer.validated_data["otp"]

            # Get OTP record
            try:
                otp_record = EmailOTP.objects.filter(email=email, otp=otp, is_verified=False).latest("created_at")
            except EmailOTP.DoesNotExist:
                response_data = {
                    "status": "400",
                    "message": "Invalid OTP",
                    "Response": []
                }
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            # Check expiry
            if otp_record.is_expired():
                response_data = {
                    "status": "400",
                    "message": "OTP expired",
                    "Response": []
                }
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            # Mark OTP as used
            otp_record.is_verified = True
            otp_record.save()

            # Get user
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                response_data = {
                    "status": "404",
                    "message": "User not found",
                    "Response": []
                }
                return Response(response_data, status=status.HTTP_404_NOT_FOUND)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            response_data = {
                "status": "200",
                "message": "OTP verified successfully",
                "Response": [
                    {
                        "id": user.id,
                        "full_name": user.full_name,
                        "email": user.email,
                        "phone_number": user.phone_number,
                        "city": user.city,
                        "state": user.state,
                        "country": user.country,
                        "profile_photo": user.profile_photo.url if user.profile_photo else None,
                        "tokens": {
                            "refresh": str(refresh),
                            "access": str(refresh.access_token),
                        },
                    }
                ]
            }

            return Response(response_data, status=status.HTTP_200_OK)

        # Validation errors
        response_data = {
            "status": "400",
            "message": "Validation errors",
            "Response": serializer.errors
        }
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)


# interest list
class InterestListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        interests = Interest.objects.all().order_by('name')
        serializer = InterestSerializer(interests, many=True)

        response_data = {
            "status": "200",
            "message": "Interests fetched successfully",
            "Response": serializer.data if serializer.data else []
        }

        return Response(response_data, status=status.HTTP_200_OK)


# add user details
class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserProfileSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            profile = serializer.save()

            response_data = {
                "status": "200",
                "message": "Profile added/updated successfully",
                "Response": [UserProfileSerializer(profile).data] if profile else []
            }
            return Response(response_data, status=status.HTTP_200_OK)

        response_data = {
            "status": "400",
            "message": "Invalid data provided",
            "Response": serializer.errors if serializer.errors else []
        }
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)


# fcm token
class UpdateFCMTokenAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        if serializer.is_valid():
            device_type = serializer.validated_data['device_type']
            fcm_token = serializer.validated_data['fcm_token']

            # Update or create token for this user
            device_obj, created = DeviceToken.objects.update_or_create(
                user=request.user,
                defaults={
                    'device_type': device_type,
                    'fcm_token': fcm_token
                }
            )

            response_data = {
                "status": "200",
                "message": "FCM token created" if created else "FCM token updated",
                "Response": [
                    {
                        "user_id": request.user.id,
                        "device_type": device_type,
                        "fcm_token": fcm_token,
                        "updated_at": device_obj.updated_at
                    }
                ]
            }

            return Response(response_data, status=status.HTTP_200_OK)

        # Validation errors
        response_data = {
            "status": "400",
            "message": "Validation errors",
            "Response": serializer.errors if serializer.errors else []
        }
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)


class RefreshAccessTokenAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh', None)

        if not refresh_token:
            return Response(
                {
                    "status": "400",
                    "message": "Refresh token is required",
                    "Response": []
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)

            response_data = {
                "status": "200",
                "message": "Access token generated successfully",
                "Response": [
                    {
                        "access": access_token
                    }
                ]
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except TokenError:
            response_data = {
                "status": "400",
                "message": "Invalid or expired refresh token",
                "Response": []
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)