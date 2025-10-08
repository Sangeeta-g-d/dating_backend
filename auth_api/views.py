from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import *
from . models import *
from django.core.mail import send_mail
from rest_framework.permissions import IsAuthenticated,AllowAny  
from rest_framework.parsers import MultiPartParser, FormParser


# user registration View
class UserRegistrationAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]  # ✅ handle image uploads

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # 🔑 Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "status": status.HTTP_201_CREATED,
                    "message": "User registered successfully",
                    "user": {
                        "id": user.id,
                        "full_name": user.full_name,
                        "email": user.email,
                        "phone_number": user.phone_number,
                        "city": user.city,
                        "state": user.state,
                        "country": user.country,
                        "profile_photo": user.profile_photo.url if user.profile_photo else None,
                    },
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": status.HTTP_400_BAD_REQUEST, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )



# user login API
class UserLoginAPIView(APIView):
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            user = serializer.validated_data["user"]

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "status": status.HTTP_200_OK,
                    "message": "Login successful",
                    "user": {
                        "id": user.id,
                        "full_name": user.full_name,
                        "email": user.email,
                        "phone_number": user.phone_number,
                        "city": user.city,
                        "state": user.state,
                        "country": user.country,
                        "profile_photo": user.profile_photo.url if user.profile_photo else None,
                    },
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "status": status.HTTP_400_BAD_REQUEST,
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    

class SendOTPAPIView(APIView):
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]

            # Check if user exists
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                return Response({"status": 404, "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

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

            return Response({"status": 200, "message": "OTP sent successfully"}, status=status.HTTP_200_OK)

        return Response({"status": 400, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPAPIView(APIView):
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            otp = serializer.validated_data["otp"]

            try:
                otp_record = EmailOTP.objects.filter(email=email, otp=otp, is_verified=False).latest("created_at")
            except EmailOTP.DoesNotExist:
                return Response({"status": 400, "message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

            # Check expiry
            if otp_record.is_expired():
                return Response({"status": 400, "message": "OTP expired"}, status=status.HTTP_400_BAD_REQUEST)

            # Mark OTP as used
            otp_record.is_verified = True
            otp_record.save()

            # Get user
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                return Response({"status": 404, "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "status": 200,
                    "message": "OTP verified successfully",
                    "user": {
                        "id": user.id,
                        "full_name": user.full_name,
                        "email": user.email,
                        "phone_number": user.phone_number,
                        "city": user.city,
                        "state": user.state,
                        "country": user.country,
                        "profile_photo": user.profile_photo.url if user.profile_photo else None,
                    },
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                },
                status=status.HTTP_200_OK,
            )

        return Response({"status": 400, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    

# interest list
class InterestListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        interests = Interest.objects.all().order_by('name')
        serializer = InterestSerializer(interests, many=True)
        return Response(
            {
                "status": status.HTTP_200_OK,
                "message": "Interests fetched successfully",
                "response": serializer.data,
            },
            status=status.HTTP_200_OK
        )


# add user details
class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserProfileSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            profile = serializer.save()
            return Response(
                {
                    "status": status.HTTP_201_CREATED,
                    "message": "Profile added/updated successfully",
                    "response": UserProfileSerializer(profile).data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            {
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid data provided",
                "response": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST
        )