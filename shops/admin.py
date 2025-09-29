from django.contrib import admin
from .models import Region, Shop, Category, ShopCategory, Dish, Review

admin.site.register(Region)
admin.site.register(Shop)
admin.site.register(Category)
admin.site.register(ShopCategory)
admin.site.register(Dish)
admin.site.register(Review)
