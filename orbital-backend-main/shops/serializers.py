from rest_framework import serializers
from .models import Category, Region, Shop, Review, Reply, Likes, Favourite, Announcement


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['category_id', 'category_name',
                  'category_image', 'category_description']
        read_only_fields = ['category_id']


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ['region_id', 'region_name']
        read_only_fields = ['region_id']


class ShopSerializer(serializers.ModelSerializer):
    review_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    has_freefood = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = '__all__'
        read_only_fields = ['shop_id', 'created_at', 'updated_at']

    def get_review_count(self, obj):
        return obj.reviews.count()

    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if not reviews.exists():
            return None
        return "{:.2f}".format(round(sum([r.rating for r in reviews]) / reviews.count(), 2))

    def get_categories(self, obj):
        return [sc.category_id for sc in obj.shop_categories.all()]

    def get_has_freefood(self, obj):
        return any(review.has_freefood for review in obj.reviews.all())


class VendorDashboardSerializer(serializers.Serializer):
    total_reviews = serializers.IntegerField()
    average_rating = serializers.FloatField()
    total_shops = serializers.IntegerField()
    monthly_growth = serializers.FloatField()
    recent_reviews = serializers.ListField()
    shops = ShopSerializer(many=True)


class ReviewSerializer(serializers.ModelSerializer):
    userReaction = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    dislike_count = serializers.SerializerMethodField()
    has_freefood = serializers.SerializerMethodField()
    profile_pic = serializers.CharField(
        source='reviewer.user.profile_pic', read_only=True)
    username = serializers.CharField(
        source='reviewer.user.username', read_only=True)

    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['review_id', 'created_at', 'reviewer',
                            'shop', 'userReaction', 'like_count', 'dislike_count']

    def get_userReaction(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        reviewer = getattr(request.user, 'reviewer_profile', None)
        if not reviewer:
            return None
        like = obj.likes.filter(reviewer=reviewer).first()
        if like:
            return True if like.likeORdislike else False
        return None

    def get_like_count(self, obj):
        return obj.likes.filter(likeORdislike=True).count()

    def get_dislike_count(self, obj):
        return obj.likes.filter(likeORdislike=False).count()

    def get_has_freefood(self, obj):
        # Only include `has_freefood` if the current user is the reviewer
        request = self.context.get('request')
        print(
            f"Request user: {request.user}, Reviewer user: {obj.reviewer.user}")
        if request and request.user.is_authenticated and obj.reviewer.user == request.user:
            return obj.has_freefood
        return None  # Hide the field for other users

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError(
                "Rating must be between 1 and 5.")
        return value


class LikesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Likes
        fields = '__all__'
        read_only_fields = ['review', 'reviewer', 'created_at']


class FavouriteSerializer(serializers.ModelSerializer):
    shop = serializers.PrimaryKeyRelatedField(queryset=Shop.objects.all())

    class Meta:
        model = Favourite
        fields = ['shop', 'created_at']
        read_only_fields = ['created_at']


class ReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = Reply
        fields = ['reply_id', 'reply_description',
                  'reply_date', 'vendor', 'review']
        read_only_fields = ['reply_id', 'reply_date', 'vendor', 'review']

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['review'] = self.context['view'].kwargs['shop_id']
        validated_data['vendor'] = request.user.reviewer_profile
        return super().create(validated_data)


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ['announcement_id', 'title', 'description',
                  'announcement_image', 'created_at', 'updated_at']
        read_only_fields = ['announcement_id', 'created_at', 'updated_at']

    def validate(self, data):
        request = self.context.get('request')
        shop_id = self.context['view'].kwargs['shop_id']
        vendor_profile = request.user.vendor_profile

        # Check shop ownership
        shop = Shop.objects.filter(
            shop_id=shop_id, vendor=vendor_profile).first()
        if not shop:
            raise serializers.ValidationError("You do not own this shop.")

        data['shop'] = shop
        return data
