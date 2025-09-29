from rest_framework.exceptions import PermissionDenied
from rest_framework import viewsets, permissions, generics, serializers
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from datetime import timedelta
from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from .models import Category, Region, Shop, Review, Reply, Likes, Favourite, Announcement, ShopCategory
from .serializers import ReviewSerializer, CategorySerializer, RegionSerializer, ShopSerializer, LikesSerializer, FavouriteSerializer, ReplySerializer, AnnouncementSerializer
from .onemap import get_latlng_from_postal
from ml.ml import detector


class CategoryView(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        return CategorySerializer


class RegionView(viewsets.ModelViewSet):
    queryset = Region.objects.all()
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        return RegionSerializer


class ShopSearchView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = Shop.objects.all()

        q = request.GET.get('q')
        if q:
            queryset = queryset.filter(shop_name__icontains=q)

        is_vegetarian = request.GET.get('is_vegetarian')
        if is_vegetarian == 'true':
            queryset = queryset.filter(is_vegetarian=True)

        is_halal = request.GET.get('is_halal')
        if is_halal == 'true':
            queryset = queryset.filter(is_halal=True)

        categories = request.GET.get('categories')
        if categories:
            cat_ids = [int(cid)
                       for cid in categories.split(',') if cid.isdigit()]
            queryset = queryset.filter(
                shop_categories__category__category_id__in=cat_ids).distinct()

        regions = request.GET.get('regions')
        if regions:
            region_ids = [int(rid)
                          for rid in regions.split(',') if rid.isdigit()]
            queryset = queryset.filter(region_id__in=region_ids).distinct()

        sort_by = request.GET.get('sort_by')
        if sort_by == 'relevance':
            queryset = queryset.annotate(num_reviews=Count(
                'reviews')).order_by('-num_reviews')
        elif sort_by == 'rating':
            queryset = queryset.annotate(avg_rating=Avg(
                'reviews__rating')).order_by('-avg_rating')
        elif sort_by == 'alphabetical':
            queryset = queryset.order_by('shop_name')
        elif sort_by == 'recent':
            queryset = queryset.order_by('-created_at')
        elif sort_by == 'favourite':
            queryset = queryset.filter(
                favourites__reviewer=request.user.reviewer_profile).distinct()

        paginator = PageNumberPagination()
        paginator.page_size = 18
        result_page = paginator.paginate_queryset(queryset, request)

        serializer = ShopSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ShopDetailView(generics.RetrieveAPIView):
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        shop_id = self.kwargs['shop_id']
        return generics.get_object_or_404(Shop, shop_id=shop_id)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vendor_dashboard(request):
    user = request.user

    if user.role != 'vendor':
        return Response({'error': 'User is not a vendor'}, status=403)

    try:
        vendor_profile = user.vendor_profile
    except:
        return Response({'error': 'Vendor profile not found'}, status=404)

    vendor_shops = Shop.objects.filter(vendor=vendor_profile)
    total_shops = vendor_shops.count()

    all_reviews = Review.objects.filter(
        shop__in=vendor_shops).order_by('-created_at')
    total_reviews = all_reviews.count()

    if total_reviews > 0:
        avg_rating = all_reviews.aggregate(
            avg_rating=Avg('rating'))['avg_rating']
        avg_rating = round(avg_rating, 1) if avg_rating else 0
    else:
        avg_rating = 0

    now = timezone.now()
    current_month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)

    if now.month == 1:
        prev_month_start = current_month_start.replace(
            year=now.year - 1, month=12)
        prev_month_end = current_month_start - timedelta(seconds=1)
    else:
        prev_month_start = current_month_start.replace(month=now.month - 1)
        prev_month_end = current_month_start - timedelta(seconds=1)

    # Count reviews for current and previous month
    current_month_reviews = all_reviews.filter(
        created_at__gte=current_month_start).count()
    prev_month_reviews = all_reviews.filter(
        created_at__gte=prev_month_start,
        created_at__lte=prev_month_end
    ).count()

    # Calculate growth percentage
    if prev_month_reviews > 0:
        monthly_growth = (
            (current_month_reviews - prev_month_reviews) / prev_month_reviews) * 100
    else:
        monthly_growth = 100 if current_month_reviews > 0 else 0

    monthly_growth = round(monthly_growth, 1)

    # Get all unreplied reviews for Tasks section
    unreplied_reviews = all_reviews.filter(
        ~Q(replies__isnull=False)  # Reviews that don't have any replies
    ).select_related('shop', 'reviewer__user')

    unreplied_reviews_data = []

    for review in unreplied_reviews:
        unreplied_reviews_data.append({
            'id': review.review_id,
            'reviewer': review.reviewer.user.username,
            'rating': review.rating,
            'comment': review.description or '',
            'date': review.created_at.strftime('%Y-%m-%d'),
            'shop': review.shop.shop_name,
            'is_replied': False  # All of these are unreplied by definition
        })

    # Get shops data with their ratings, review counts, and performance analysis
    shops_data = []
    shops_needing_attention = 0
    shops_trending_down = 0
    total_shop_ratings = []

    for shop in vendor_shops:
        shop_reviews = Review.objects.filter(shop=shop)
        review_count = shop_reviews.count()

        if review_count > 0:
            shop_avg_rating = shop_reviews.aggregate(
                avg_rating=Avg('rating'))['avg_rating']
            shop_avg_rating = round(
                shop_avg_rating, 1) if shop_avg_rating else 0
            total_shop_ratings.append(shop_avg_rating)

            # Check if shop needs attention (rating < 3.5)
            needs_attention = shop_avg_rating < 3.5
            if needs_attention:
                shops_needing_attention += 1

            # Check for declining trend (last 7 days vs previous 7 days)
            last_week = now - timedelta(days=7)
            prev_week = now - timedelta(days=14)

            recent_reviews = shop_reviews.filter(created_at__gte=last_week)
            previous_reviews = shop_reviews.filter(
                created_at__gte=prev_week, created_at__lt=last_week)

            recent_avg = recent_reviews.aggregate(avg_rating=Avg('rating'))[
                'avg_rating'] if recent_reviews.exists() else None
            previous_avg = previous_reviews.aggregate(avg_rating=Avg('rating'))[
                'avg_rating'] if previous_reviews.exists() else None

            trending_down = False
            if recent_avg and previous_avg and recent_avg < (previous_avg - 0.2):
                trending_down = True
                if not needs_attention:  # Only count if not already in attention category
                    shops_trending_down += 1

        else:
            shop_avg_rating = 0
            needs_attention = False
            trending_down = False

        # Get shop's primary category (first category if multiple)
        shop_category = shop.shop_categories.first()
        category_name = shop_category.category.category_name if shop_category else 'General'

        shops_data.append({
            'id': shop.shop_id,
            'name': shop.shop_name,
            'rating': shop_avg_rating,
            'reviewCount': review_count,
            'category': category_name,
            'needsAttention': needs_attention,
            'trendingDown': trending_down
        })

    # Sort shops by rating (highest first)
    shops_data.sort(key=lambda x: x['rating'], reverse=True)

    # Calculate shop performance status
    if shops_needing_attention > 0:
        shop_status = f"{shops_needing_attention} need attention"
        shop_status_type = "critical"
    elif shops_trending_down > 0:
        shop_status = f"{shops_trending_down} trending down"
        shop_status_type = "warning"
    else:
        if total_shop_ratings:
            lowest_rating = min(total_shop_ratings)
            if lowest_rating >= 4.0:
                shop_status = "All performing excellently"
                shop_status_type = "excellent"
            else:
                shop_status = f"All performing well"
                shop_status_type = "good"
        else:
            shop_status = "No reviews yet"
            shop_status_type = "neutral"

    # Calculate actual rating distribution
    rating_distribution = {
        5: all_reviews.filter(rating=5).count(),
        4: all_reviews.filter(rating=4).count(),
        3: all_reviews.filter(rating=3).count(),
        2: all_reviews.filter(rating=2).count(),
        1: all_reviews.filter(rating=1).count()
    }

    return Response({
        'total_reviews': total_reviews,
        'average_rating': avg_rating,
        'total_shops': total_shops,
        'monthly_growth': monthly_growth,
        'recent_reviews': unreplied_reviews_data,
        'shops': shops_data,
        'shop_performance': {
            'status': shop_status,
            'type': shop_status_type,
            'shops_needing_attention': shops_needing_attention,
            'shops_trending_down': shops_trending_down
        },
        'rating_distribution': rating_distribution
    })

# Vendor Reviews API for Reviews Page


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vendor_reviews(request):
    """
    Vendor Reviews API endpoint for the /vendor/reviews page
    Returns all reviews for the vendor's shops with filtering options
    """
    user = request.user

    # Check if user is a vendor
    if user.role != 'vendor':
        return Response({'error': 'User is not a vendor'}, status=403)

    try:
        vendor_profile = user.vendor_profile
    except Exception as e:
        return Response({'error': f'Vendor profile not found: {str(e)}'}, status=404)

    vendor_shops = Shop.objects.filter(vendor=vendor_profile)

    reviews_queryset = Review.objects.filter(shop__in=vendor_shops).select_related(
        'shop', 'reviewer__user'
    ).order_by('-created_at')

    # Apply filters from query parameters
    rating_filter = request.GET.get('rating')  # e.g., '5', '4', '3', '2', '1'
    unreplied_only = request.GET.get('unreplied')  # 'true' or 'false'

    if rating_filter and rating_filter.isdigit():
        reviews_queryset = reviews_queryset.filter(rating=int(rating_filter))

    if unreplied_only == 'true':
        # Filter reviews that don't have any replies
        reviews_queryset = reviews_queryset.filter(replies__isnull=True)

    # Serialize the reviews data with reply information
    reviews_data = []
    for review in reviews_queryset:
        # Get the reply for this review (if any)
        reply = review.replies.first()

        reply_data = None
        if reply:
            reply_data = {
                'reply_id': reply.reply_id,
                'reply_description': reply.reply_description,
                'reply_date': reply.reply_date.strftime('%Y-%m-%d %I:%M %p')
            }

        reviews_data.append({
            'id': review.review_id,
            'reviewer_name': review.reviewer.user.username,
            'shop_name': review.shop.shop_name,
            'rating': review.rating,
            'comment': review.description or '',
            'date': review.created_at.strftime('%Y-%m-%d'),
            'time': review.created_at.strftime('%I:%M %p'),
            'reply': reply_data
        })

    return Response({
        'reviews': reviews_data,
        'total_count': len(reviews_data)
    })

# Reply to Review API - Updated to use Reply model


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reply_to_review(request, review_id):
    """
    API endpoint for vendors to reply to reviews using the Reply model
    """
    user = request.user

    # Check if user is a vendor
    if user.role != 'vendor':
        return Response({'error': 'User is not a vendor'}, status=403)

    try:
        vendor_profile = user.vendor_profile
    except:
        return Response({'error': 'Vendor profile not found'}, status=404)

    try:
        review = Review.objects.get(
            review_id=review_id, shop__vendor=vendor_profile)
    except Review.DoesNotExist:
        return Response({'error': 'Review not found or access denied'}, status=404)

    # Check if vendor already replied to this review
    existing_reply = Reply.objects.filter(
        review=review, vendor=vendor_profile).first()
    if existing_reply:
        return Response({'error': 'You have already replied to this review'}, status=400)

    reply_description = request.data.get('reply_description')
    if not reply_description:
        return Response({'error': 'Reply description is required'}, status=400)

    # Create new Reply record
    reply = Reply.objects.create(
        vendor=vendor_profile,
        review=review,
        reply_description=reply_description,
        reply_date=timezone.now()
    )

    return Response({
        'message': 'Reply posted successfully',
        'reply': {
            'reply_id': reply.reply_id,
            'reply_description': reply.reply_description,
            'reply_date': reply.reply_date.strftime('%Y-%m-%d %I:%M %p')
        }
    })


class ReviewView(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Review.objects.filter(shop_id=self.kwargs['shop_id'])
        sort = self.request.GET.get('sort')

        if sort == 'most_liked':
            queryset = queryset.annotate(
                like_count=Count('likes', filter=Q(likes__likeORdislike=True))
            ).order_by('-like_count', '-created_at')
        elif sort == 'most_disliked':
            queryset = queryset.annotate(
                dislike_count=Count('likes', filter=Q(
                    likes__likeORdislike=False))
            ).order_by('-dislike_count', '-created_at')
        elif sort == 'newest':
            queryset = queryset.order_by('-created_at')
        elif sort == 'highest_rating':
            queryset = queryset.order_by('-rating')
        elif sort == 'lowest_rating':
            queryset = queryset.order_by('rating')

        return queryset

    def perform_create(self, serializer):
        if not self.request.user.is_authenticated:
            raise serializers.ValidationError(
                "You must be logged in to create a review."
            )
        # Prevent duplicate reviews by the same reviewer for the same shop
        if Review.objects.filter(shop_id=self.kwargs['shop_id'], reviewer=self.request.user.reviewer_profile).exists():
            raise serializers.ValidationError(
                "You have already reviewed this shop."
            )

        result = detector(self.request.data.get('description', ''))
        label = result[0]['label']
        if (label == 'Human'):
            is_ai_generated = False
        elif (label == 'ChatGPT'):
            is_ai_generated = True
        score = result[0]['score']

        # Save the review
        review = serializer.save(
            reviewer=self.request.user.reviewer_profile,
            shop_id=self.kwargs['shop_id'],
            has_freefood=self.request.data.get('has_freefood', False),
            is_ai_generated=is_ai_generated,
            score=score
        )

    def perform_update(self, serializer):
        if not self.request.user.is_authenticated:
            raise serializers.ValidationError(
                "You must be logged in to update a review.")
        # Ensure the reviewer can only update their own reviews
        if serializer.instance.reviewer != self.request.user.reviewer_profile:
            raise serializers.ValidationError(
                "You can only update your own reviews.")

        result = detector(self.request.data.get('description', ''))
        label = result[0]['label']
        if (label == 'Human'):
            is_ai_generated = False
        elif (label == 'ChatGPT'):
            is_ai_generated = True
        score = result[0]['score']

        serializer.save(
            reviewer=self.request.user.reviewer_profile,
            shop_id=self.kwargs['shop_id'],
            has_freefood=self.request.data.get('has_freefood', False),
            is_ai_generated=is_ai_generated,
            score=score
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        reviews = Review.objects.filter(shop_id=self.kwargs['shop_id'])
        context['reviews'] = reviews
        return context


class LikeDetailView(CreateAPIView):
    serializer_class = LikesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, shop_id, review_id):  # upsert
        reviewer = request.user.reviewer_profile
        likeORdislike = request.data.get('likeORdislike')
        if likeORdislike is None:
            return Response({'detail': 'likeORdislike is required.'}, status=400)
        existing = Likes.objects.filter(
            review_id=review_id, reviewer=reviewer).first()
        if existing:
            existing.likeORdislike = likeORdislike
            existing.save()
            serializer = LikesSerializer(existing)
            return Response(serializer.data, status=200)
        else:
            like = Likes.objects.create(
                reviewer=reviewer,
                review_id=review_id,
                likeORdislike=likeORdislike
            )
            serializer = LikesSerializer(like)
            return Response(serializer.data, status=201)

    def delete(self, request, shop_id, review_id):
        reviewer = request.user.reviewer_profile
        existing = Likes.objects.filter(
            review_id=review_id, reviewer=reviewer).first()
        if existing:
            existing.delete()
            return Response({'detail': 'Like/dislike removed.'}, status=204)
        else:
            return Response({'detail': 'No like/dislike to remove.'}, status=404)

    def get_queryset(self):
        # Only allow the reviewer to delete their own like/dislike
        return Likes.objects.filter(reviewer=self.request.user.reviewer_profile)


class FavouriteView(viewsets.ModelViewSet):
    queryset = Favourite.objects.all()
    serializer_class = FavouriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        # Retrieve shop_id from URL parameters
        shop_id = self.kwargs.get('shop_id')
        if not shop_id:
            return Response({'detail': 'shop_id is required.'}, status=400)

        try:
            shop = Shop.objects.get(shop_id=shop_id)
        except Shop.DoesNotExist:
            return Response({'detail': 'Invalid shop ID.'}, status=404)

        # Check if the favorite already exists
        existing_favorite = Favourite.objects.filter(
            shop=shop, reviewer=request.user.reviewer_profile
        ).first()

        if existing_favorite:
            return Response({'detail': 'You have already favorited this shop.'}, status=400)

        # Create a new favorite
        favourite = Favourite.objects.create(
            reviewer=request.user.reviewer_profile,
            shop=shop
        )
        serializer = self.get_serializer(favourite)
        return Response(serializer.data, status=201)

    def list(self, request, *args, **kwargs):
        # List all favorites for the current user
        favorites = Favourite.objects.filter(
            reviewer=request.user.reviewer_profile).select_related('shop')
        serializer = self.get_serializer(favorites, many=True)
        return Response(serializer.data, status=200)

    def destroy(self, request, *args, **kwargs):
        # Retrieve shop_id from URL parameters
        shop_id = self.kwargs.get('shop_id')
        if not shop_id:
            return Response({'detail': 'shop_id is required.'}, status=400)

        try:
            shop = Shop.objects.get(shop_id=shop_id)
        except Shop.DoesNotExist:
            return Response({'detail': 'Invalid shop ID.'}, status=404)

        # Ensure the favorite exists and belongs to the current user
        favorite = Favourite.objects.filter(
            shop=shop, reviewer=request.user.reviewer_profile
        ).first()

        if not favorite:
            return Response({'detail': 'Favorite not found.'}, status=404)

        # Delete the favorite
        favorite.delete()
        return Response({'detail': 'Favorite removed.'}, status=200)


class ReplyView(viewsets.ModelViewSet):
    serializer_class = ReplySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        if shop_id:
            return Reply.objects.filter(review__shop_id=shop_id).select_related('review', 'vendor')
        return Reply.objects.none()


class PublicAnnouncementView(viewsets.ReadOnlyModelViewSet):
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        shop_id = self.kwargs.get('shop_id')
        if shop_id:
            # Filter announcements by shop_id
            return Announcement.objects.filter(shop_id=shop_id).order_by('-created_at')
        # Return an empty queryset if shop_id is not provided
        return Announcement.objects.none()


class AnnouncementView(viewsets.ModelViewSet):
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Get shop_id from the URL parameters
        shop_id = self.kwargs.get('shop_id')
        vendor_profile = self.request.user.vendor_profile

        if shop_id:
            # Check if the shop belongs to the vendor
            shop = Shop.objects.filter(
                shop_id=shop_id, vendor=vendor_profile).first()
            if not shop:
                raise PermissionDenied({"detail": "You do not own this shop."})

            # Filter announcements by shop_id
            return Announcement.objects.filter(shop_id=shop_id).order_by('-created_at')

        # Return an empty queryset if shop_id is not provided
        return Announcement.objects.none()

    def perform_create(self, serializer):
        # Get the shop_id from the URL
        shop_id = self.kwargs['shop_id']

        # Check if the shop belongs to the vendor
        vendor_profile = self.request.user.vendor_profile
        shop = Shop.objects.filter(
            shop_id=shop_id, vendor=vendor_profile).first()

        if not shop:
            raise PermissionDenied({"detail": "You do not own this shop."})

        # Save the announcement with the shop
        serializer.save(shop=shop)


class AnnouncementDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        announcement_id = self.kwargs['announcement_id']
        vendor_profile = self.request.user.vendor_profile

        # Filter announcements based on the shop's vendor
        return generics.get_object_or_404(
            Announcement,
            announcement_id=announcement_id,
            shop__vendor=vendor_profile
        )

# Vendor Shop Management API


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vendor_shops(request):
    """
    Get all shops for the logged-in vendor
    """
    user = request.user

    if user.role != 'vendor':
        return Response({'error': 'User is not a vendor'}, status=403)

    try:
        vendor_profile = user.vendor_profile
    except:
        return Response({'error': 'Vendor profile not found'}, status=404)

    # Get vendor's shops with review data
    shops = Shop.objects.filter(vendor=vendor_profile)
    shops_data = []

    for shop in shops:
        shop_reviews = Review.objects.filter(shop=shop)
        review_count = shop_reviews.count()

        if review_count > 0:
            avg_rating = shop_reviews.aggregate(
                avg_rating=Avg('rating'))['avg_rating']
            avg_rating = round(avg_rating, 1) if avg_rating else 0
        else:
            avg_rating = 0

        # Get shop's primary category
        shop_category = shop.shop_categories.first()
        category_name = shop_category.category.category_name if shop_category else 'General'

        shops_data.append({
            'id': shop.shop_id,
            'name': shop.shop_name,
            'rating': avg_rating,
            'reviewCount': review_count,
            'category': category_name,
            'status': 'active' if shop.claim_status else 'inactive',
            'created_at': shop.created_at.isoformat() if hasattr(shop, 'created_at') else '2025-01-01T00:00:00Z'
        })

    return Response({'shops': shops_data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_vendor_shop(request):
    """
    Create a new shop for the logged-in vendor
    """
    user = request.user

    if user.role != 'vendor':
        return Response({'error': 'User is not a vendor'}, status=403)

    try:
        vendor_profile = user.vendor_profile
    except:
        return Response({'error': 'Vendor profile not found'}, status=404)

    try:
        # Create shop
        postal_code = request.data.get('postal_code')
        lat, lng = get_latlng_from_postal(postal_code)
        shop = Shop.objects.create(
            shop_name=request.data.get('shop_name'),
            shop_description=request.data.get('shop_description'),
            shop_image=request.FILES.get('shop_image'),
            vendor=vendor_profile,
            region_id=request.data.get('region'),
            is_halal=request.data.get('is_halal', 'false').lower() == 'true',
            is_vegetarian=request.data.get(
                'is_vegetarian', 'false').lower() == 'true',
            claim_status=request.data.get(
                'claim_status', 'true').lower() == 'true',
            address_line1=request.data.get('address1'),
            address_line2=request.data.get('address2', ''),
            postal_code=postal_code,
            latitude=lat,
            longitude=lng,
        )

        return Response({
            'shop_id': shop.shop_id,
            'shop_name': shop.shop_name,
            'shop_image': shop.shop_image.url if shop.shop_image else None,
            'message': 'Shop created successfully'
        }, status=201)

    except Exception as e:
        return Response({
            'error': f'Failed to create shop: {str(e)}'
        }, status=400)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_vendor_shop(request, shop_id):
    """
    Update an existing shop for the logged-in vendor
    """
    user = request.user

    if user.role != 'vendor':
        return Response({'error': 'User is not a vendor'}, status=403)

    try:
        vendor_profile = user.vendor_profile
    except:
        return Response({'error': 'Vendor profile not found'}, status=404)

    try:
        # Get the shop and verify ownership
        shop = Shop.objects.get(shop_id=shop_id, vendor=vendor_profile)
    except Shop.DoesNotExist:
        return Response({'error': 'Shop not found or access denied'}, status=404)

    try:
        # Update shop fields
        shop.shop_name = request.data.get('shop_name', shop.shop_name)
        shop.shop_description = request.data.get(
            'shop_description', shop.shop_description)
        shop.region_id = request.data.get('region', shop.region_id)
        shop.is_halal = request.data.get('is_halal', 'false').lower() == 'true'
        shop.is_vegetarian = request.data.get(
            'is_vegetarian', 'false').lower() == 'true'
        shop.claim_status = request.data.get(
            'claim_status', 'true').lower() == 'true'
        shop.address_line1 = request.data.get('address1', shop.address_line1)
        shop.address_line2 = request.data.get(
            'address2', shop.address_line2 or '')

        # Update postal code and coordinates if postal code changed
        postal_code = request.data.get('postal_code')
        if postal_code and postal_code != shop.postal_code:
            lat, lng = get_latlng_from_postal(postal_code)
            shop.postal_code = postal_code
            shop.latitude = lat
            shop.longitude = lng

        # Update image if provided
        if 'shop_image' in request.FILES:
            shop.shop_image = request.FILES['shop_image']

        shop.save()

        # Update shop category if provided
        category_id = request.data.get('category')
        if category_id:
            # Clear existing categories and add new one
            shop.shop_categories.all().delete()
            try:
                category = Category.objects.get(category_id=category_id)
                ShopCategory.objects.create(shop=shop, category=category)
            except Category.DoesNotExist:
                pass  # Ignore invalid category

        return Response({
            'shop_id': shop.shop_id,
            'shop_name': shop.shop_name,
            'shop_image': shop.shop_image.url if shop.shop_image else None,
            'message': 'Shop updated successfully'
        }, status=200)

    except Exception as e:
        return Response({
            'error': f'Failed to update shop: {str(e)}'
        }, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_shop_category(request, shop_id):
    """
    Add a category to a vendor's shop
    """
    user = request.user

    if user.role != 'vendor':
        return Response({'error': 'User is not a vendor'}, status=403)

    try:
        vendor_profile = user.vendor_profile
        shop = Shop.objects.get(shop_id=shop_id, vendor=vendor_profile)
    except Shop.DoesNotExist:
        return Response({'error': 'Shop not found or access denied'}, status=404)

    try:
        from .models import ShopCategory, Category
        category_id = request.data.get('category_id')
        category = Category.objects.get(category_id=category_id)

        # Create or get shop category relationship
        ShopCategory.objects.get_or_create(
            shop=shop,
            category=category
        )

        return Response({
            'message': 'Category added successfully'
        }, status=201)

    except Category.DoesNotExist:
        return Response({'error': 'Category not found'}, status=404)
    except Exception as e:
        return Response({
            'error': f'Failed to add category: {str(e)}'
        }, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reviewer_dashboard(request):
    """
    Get reviewer dashboard data including stats and recent activity
    """
    user = request.user

    if user.role != 'reviewer':
        return Response({'error': 'User is not a reviewer'}, status=403)

    try:
        reviewer_profile = user.reviewer_profile
    except Exception as e:
        return Response({'error': f'Reviewer profile not found: {str(e)}'}, status=400)

    try:

        # Get current date for this month calculations
        current_date = timezone.now()
        current_month_start = current_date.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)

        # Calculate stats
        total_reviews = Review.objects.filter(
            reviewer=reviewer_profile).count()

        total_shops_reviewed = Review.objects.filter(
            reviewer=reviewer_profile).values('shop').distinct().count()
        total_likes_received = Likes.objects.filter(
            review__reviewer=reviewer_profile, likeORdislike=True).count()
        reviews_this_month = Review.objects.filter(
            reviewer=reviewer_profile,
            created_at__gte=current_month_start
        ).count()

        # Get recent reviews (last 5)
        recent_reviews = Review.objects.filter(
            reviewer=reviewer_profile).select_related('shop').order_by('-created_at')[:5]
        recent_reviews_data = []
        for review in recent_reviews:
            likes_count = Likes.objects.filter(
                review=review, likeORdislike=True).count()
            recent_reviews_data.append({
                'review_id': review.review_id,
                'shop_name': review.shop.shop_name,
                'rating': review.rating,
                'description': review.description,
                'created_at': review.created_at,
                'likes_count': likes_count,
                'has_freefood': review.has_freefood
            })

        # Get recently visited shops (shops user has reviewed, ordered by most recent review)
        visited_shops_data = []
        try:
            reviewed_shops = Review.objects.filter(reviewer=reviewer_profile).select_related(
                'shop').order_by('-created_at').values_list('shop', flat=True).distinct()[:6]
            for shop_id in reviewed_shops:
                try:
                    shop = Shop.objects.get(shop_id=shop_id)
                    # Get review count and average rating for this shop
                    shop_stats = Review.objects.filter(shop=shop).aggregate(
                        review_count=Count('review_id'),
                        avg_rating=Avg('rating')
                    )
                    # Get shop category (required during shop creation)
                    category = shop.shop_categories.first().category.category_name

                    visited_shops_data.append({
                        'shop_id': shop.shop_id,
                        'shop_name': shop.shop_name,
                        'shop_image': shop.shop_image.url if shop.shop_image else None,
                        'review_count': shop_stats['review_count'] or 0,
                        'avg_rating': float(shop_stats['avg_rating'] or 0),
                        'category': category
                    })
                except Shop.DoesNotExist:
                    continue
        except Exception as e:
            visited_shops_data = []

        return Response({
            'stats': {
                'total_reviews': total_reviews,
                'total_shops_reviewed': total_shops_reviewed,
                'total_likes_received': total_likes_received,
                'reviews_this_month': reviews_this_month
            },
            'recent_reviews': recent_reviews_data,
            'recently_visited_shops': visited_shops_data
        })

    except Exception as e:
        return Response({
            'error': f'Failed to get dashboard data: {str(e)}'
        }, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reviewer_reviews(request):
    try:
        reviewer = request.user.reviewer_profile
        
        reviews_queryset = Review.objects.filter(reviewer=reviewer).select_related('shop').order_by('-created_at')
        
        paginator = PageNumberPagination()
        paginator.page_size = 10
        result_page = paginator.paginate_queryset(reviews_queryset, request)
        
        reviews_data = []
        for review in result_page:
            likes_count = Likes.objects.filter(review=review).count()
            reviews_data.append({
                'review_id': review.review_id,
                'shop_name': review.shop.shop_name,
                'shop_id': review.shop.shop_id,
                'rating': review.rating,
                'description': review.description,
                'created_at': review.created_at.strftime('%b %d, %Y'),
                'likes_count': likes_count,
                'has_freefood': review.has_freefood
            })
        
        return paginator.get_paginated_response(reviews_data)
        
    except Exception as e:
        return Response({
            'error': f'Failed to get reviewer reviews: {str(e)}'
        }, status=400)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_vendor_shop(request, shop_id):
    user = request.user
    
    if user.role != 'vendor':
        return Response({'error': 'User is not a vendor'}, status=403)
    
    try:
        vendor_profile = user.vendor_profile
    except:
        return Response({'error': 'Vendor profile not found'}, status=404)
    
    try:
        shop = Shop.objects.get(shop_id=shop_id, vendor=vendor_profile)
        shop.delete()
        return Response({'message': 'Shop deleted successfully'}, status=200)
    except Shop.DoesNotExist:
        return Response({'error': 'Shop not found or access denied'}, status=404)
    except Exception as e:
        return Response({'error': f'Failed to delete shop: {str(e)}'}, status=400)
