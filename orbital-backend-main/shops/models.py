from django.db import models
from users.models import Vendor, Reviewer
from django.utils import timezone


class Region(models.Model):
    region_id = models.AutoField(primary_key=True)
    region_name = models.CharField(max_length=255)

    def __str__(self):
        return f"Region {self.region_id}: {self.region_name}"


class Shop(models.Model):
    shop_id = models.AutoField(primary_key=True)
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name='shops',
        blank=True,
        null=True,
    )
    shop_name = models.CharField(max_length=255)
    shop_image = models.ImageField(
        upload_to='shop_images/', blank=True, null=True)
    shop_description = models.TextField(blank=True, null=True)
    is_halal = models.BooleanField(default=False)
    is_vegetarian = models.BooleanField(default=False)
    region = models.ForeignKey(
        Region, on_delete=models.CASCADE, related_name='shops')
    claim_status = models.BooleanField(default=False)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True)
    postal_code = models.CharField(max_length=20)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"Shop {self.shop_id} (Vendor {self.vendor.vendor_id if self.vendor else 'None'}, Region {self.region.region_id})"


class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=255)
    category_image = models.CharField(
        max_length=255, blank=True, null=True)
    category_description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Category {self.category_id}: {self.category_name}"


class ShopCategory(models.Model):
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name='shop_categories')
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='shops')

    class Meta:
        unique_together = ('shop', 'category')

    def __str__(self):
        return f"Shop {self.shop.shop_id} - Category {self.category.category_id}"


class Dish(models.Model):
    dish_id = models.AutoField(primary_key=True)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name='dishes')
    dish_name = models.CharField(max_length=255)
    dish_description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_vegetarian = models.BooleanField(default=False)
    is_halal = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Dish {self.dish_id} (Shop {self.shop.shop_id}): {self.dish_name}"


class Review(models.Model):
    review_id = models.AutoField(primary_key=True)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(
        Reviewer, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField()
    has_freefood = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_ai_generated = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=5, decimal_places=4, default=100.00)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"Review {self.review_id} for Shop {self.shop.shop_id} by Reviewer {self.reviewer.reviewer_id}"


class Reply(models.Model):
    reply_id = models.AutoField(primary_key=True)
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name='replies')
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name='replies')
    reply_description = models.TextField()
    reply_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Reply {self.reply_id} by Vendor {self.vendor.vendor_id} to Review {self.review.review_id}"


class Likes(models.Model):
    reviewer = models.ForeignKey(
        Reviewer, on_delete=models.CASCADE, related_name='likes')
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name='likes')
    likeORdislike = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)


class Announcement(models.Model):
    announcement_id = models.AutoField(primary_key=True)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=255, null=False, blank=False)
    announcement_image = models.ImageField(
        upload_to='announcement_images/', blank=True, null=True)
    description = models.TextField(max_length=1000)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class Favourite(models.Model):
    reviewer = models.ForeignKey(
        Reviewer, on_delete=models.CASCADE, related_name='favourites')
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name='favourites')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('reviewer', 'shop')

    def __str__(self):
        return f"Favourite {self.id} by Reviewer {self.reviewer.reviewer_id} for Shop {self.shop.shop_id}"
