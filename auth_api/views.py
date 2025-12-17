from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from chat.models import MessageReceipt
from notifications.models import Notification
from .serializers import *
from . models import *
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.core.mail import send_mail
from rest_framework.permissions import IsAuthenticated,AllowAny  
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status, permissions
from swipe_feature.models import Match
from django.db.models import Q
from ask_me_feature.models import Question
# user registration View
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
                    # REMOVE THIS LINE - S3 storage doesn't support .path
                    # print(f"   - path: {getattr(user.profile_photo, 'path', 'No path attribute')}")
                    
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
                        "qr_code_id":user.qr_uuid,
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
                        "qr_code_id":user.qr_uuid,
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
        

# user profile
class UserDetailsProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Retrieve logged-in user's profile with total posts and matches"""
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response({
                "status": "404",
                "message": "Profile not found",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = UserDetailsSerializer(profile)

        # --- Count user posts ---
        total_posts = Post.objects.filter(user=request.user).count()

        # --- Count user matches ---
        total_matches = Match.objects.filter(
            Q(user1=request.user) | Q(user2=request.user)
        ).count()
        total_questions_asked = Question.objects.filter(author=request.user).count()
        response_data = {
            "status": "200",
            "message": "Profile fetched successfully",
            "Response": [{
                **serializer.data,
                "total_posts": total_posts,
                "total_matches": total_matches,
                "total_questions_asked": total_questions_asked 
            }]
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def put(self, request):
        """Update full profile"""
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response({
                "status": "404",
                "message": "Profile not found",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = UserDetailsSerializer(profile, data=request.data)
        if serializer.is_valid():
            serializer.save()
            response_data = {
                "status": "200",
                "message": "Profile updated successfully",
                "Response": [serializer.data]
            }
            return Response(response_data, status=status.HTTP_200_OK)
        return Response({
            "status": "400",
            "message": "Validation error",
            "Response": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        """Partially update profile"""
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response({
                "status": "404",
                "message": "Profile not found",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = UserDetailsSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            response_data = {
                "status": "200",
                "message": "Profile updated successfully",
                "Response": [serializer.data]
            }
            return Response(response_data, status=status.HTTP_200_OK)
        return Response({
            "status": "400",
            "message": "Validation error",
            "Response": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    

# logged in user posts and also delete post
class UserFeedAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Fetch all posts of the logged-in user (feed)
        """
        posts = Post.objects.filter(user=request.user).order_by('-created_at')
        serializer = PostSerializer(posts, many=True)

        response_data = {
            "status": "200",
            "message": "User feed fetched successfully",
            "Response": serializer.data if serializer.data else []
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def delete(self, request, pk=None):
        """
        Delete a post by ID (only if it belongs to the logged-in user)
        """
        if not pk:
            return Response({
                "status": "400",
                "message": "Post ID is required",
                "Response": []
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            post = Post.objects.get(id=pk, user=request.user)
        except Post.DoesNotExist:
            return Response({
                "status": "404",
                "message": "Post not found or unauthorized access",
                "Response": []
            }, status=status.HTTP_404_NOT_FOUND)

        post.delete()
        return Response({
            "status": "200",
            "message": "Post deleted successfully",
            "Response": []
        }, status=status.HTTP_200_OK)
    

# search
class UserSearchAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        search = request.GET.get("search", "")
        religion = request.GET.get("religion", "")
        looking_for = request.GET.get("looking_for", "")
        gender = request.GET.get("gender", "")

        min_age = request.GET.get("min_age")
        max_age = request.GET.get("max_age")

        queryset = CustomUser.objects.select_related("profile").all()

        # --- Search by full_name ---
        if search:
            queryset = queryset.filter(full_name__icontains=search)

        # --- Filter by religion ---
        if religion:
            queryset = queryset.filter(profile__religion__iexact=religion)

        # --- Filter by looking_for ---
        if looking_for:
            queryset = queryset.filter(profile__looking_for__iexact=looking_for)

        # --- Filter by gender ---
        if gender:
            queryset = queryset.filter(profile__gender__iexact=gender)

        # -------- AGE RANGE FILTERING --------
        from datetime import date, timedelta
        today = date.today()

        if max_age:
            max_age = int(max_age)
            max_birthdate = date(today.year - max_age, today.month, today.day)
            queryset = queryset.filter(profile__date_of_birth__lte=max_birthdate)

        if min_age:
            min_age = int(min_age)
            min_birthdate = date(today.year - min_age - 1, today.month, today.day) + timedelta(days=1)
            queryset = queryset.filter(profile__date_of_birth__gte=min_birthdate)

        # -------------------------------------

        serializer = UserSearchSerializer(
            queryset, many=True, context={"request": request}
        )

        return Response({
            "status": "200",
            "message": "Users fetched successfully",
            "Response": serializer.data,
        })


class DashboardOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # -------------------- 🔹 Unread message count --------------------
        unread_messages = MessageReceipt.objects.filter(
            user=user,
            seen_at__isnull=True
        ).count()

        # -------------------- 🔹 Unread notifications count ---------------
        unread_notifications = Notification.objects.filter(
            user=user, is_read=False
        ).count()

        # -------------------- 🔹 Subscription check ----------------------
        subscription = getattr(user, "subscription", None)

        is_subscribed = False
        expiry_days_left = None

        if subscription and subscription.is_active:
            is_subscribed = True
            expiry_days_left = subscription.remaining_days()

        # -------------------- 🔹 Response -------------------------------
        return Response({
            "status": 200,
            "message": "Dashboard stats fetched successfully",
            "Response": {
                "unread_messages": unread_messages,
                "unread_notifications": unread_notifications,
                "is_subscribed": is_subscribed,
                "subscription_expiry_days_left": expiry_days_left if is_subscribed else None
            }
        })
    

class GetMyQRUUIDAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "status": "200",
            "message": "QR UUID fetched successfully",
            "Response": {
                "uuid": str(request.user.qr_uuid)  # ensure proper JSON string format
            }
        })


class QRMatchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Creates a match instantly when user scans another user's QR UUID.
        """
        scanned_uuid = request.data.get("uuid")

        if not scanned_uuid:
            return Response({
                "status": "400",
                "message": "UUID is required",
                "Response": None
            }, status=400)

        # Fetch the scanned user
        try:
            scanned_user = CustomUser.objects.get(qr_uuid=scanned_uuid)
        except CustomUser.DoesNotExist:
            return Response({
                "status": "400",
                "message": "Invalid QR UUID",
                "Response": None
            }, status=400)

        current_user = request.user

        # Prevent self-matching
        if current_user == scanned_user:
            return Response({
                "status": "400",
                "message": "You cannot match with yourself",
                "Response": None
            }, status=400)

        # Create instant match
        match = Match.create_match(current_user, scanned_user)

        return Response({
            "status": "200",
            "message": "Match created successfully",
            "Response": {
                "match_id": match.id,
                "matched_with": scanned_user.id
            }
        })


class UpdateUserLocationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        """
        Add or update latitude and longitude of logged-in user
        """
        user = request.user

        profile, created = UserProfile.objects.get_or_create(user=user)

        serializer = UserLocationUpdateSerializer(
            profile,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response({
                "status": "200",
                "message": "User location updated successfully",
                "Response": serializer.data
            }, status=status.HTTP_200_OK)

        return Response({
            "status": "400",
            "message": "Validation error",
            "Response": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)