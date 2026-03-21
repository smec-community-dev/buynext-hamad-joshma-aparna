from django.contrib import admin

from .models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    Review,
    Wishlist,
    WishlistItem,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    raw_id_fields = ("variant", "seller")
    autocomplete_fields = ("variant", "seller")
    search_fields = ("variant__sku_code", "variant__product__name", "seller__store_name")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "order_status", "is_paid", "final_amount", "ordered_at")
    list_filter = ("order_status", "is_paid", "ordered_at")
    search_fields = ("order_number", "user__username", "user__email")
    ordering = ("-ordered_at",)
    raw_id_fields = ("user",)
    autocomplete_fields = ("user",)
    inlines = [OrderItemInline]
    readonly_fields = ("order_number", "ordered_at", "updated_at")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "variant", "seller", "quantity", "item_status")
    list_filter = ("item_status",)
    search_fields = ("order__order_number", "variant__sku_code", "variant__product__name")
    raw_id_fields = ("order", "variant", "seller")
    autocomplete_fields = ("order", "variant", "seller")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")
    search_fields = ("user__username", "user__email")
    raw_id_fields = ("user",)
    autocomplete_fields = ("user",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "variant", "quantity", "added_at")
    search_fields = ("cart__user__username", "variant__sku_code", "variant__product__name")
    raw_id_fields = ("cart", "variant")
    autocomplete_fields = ("cart", "variant")


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "wishlist_name", "is_public", "created_at")
    search_fields = ("user__username", "user__email", "wishlist_name")
    raw_id_fields = ("user",)
    autocomplete_fields = ("user",)


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("wishlist", "variant", "added_at")
    search_fields = ("wishlist__user__username", "variant__sku_code", "variant__product__name")
    raw_id_fields = ("wishlist", "variant")
    autocomplete_fields = ("wishlist", "variant")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "rating", "is_verified_purchase", "is_approved", "created_at")
    list_filter = ("rating", "is_verified_purchase", "is_approved")
    search_fields = ("user__username", "product__name", "title")
