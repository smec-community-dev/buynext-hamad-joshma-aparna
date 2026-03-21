from django.contrib import admin
from .models import (
    SellerProfile,
    Product,
    ProductVariant,
    ProductImage,
    Attribute,
    AttributeOption,
    VariantAttributeBridge,
    InventoryLog,
)


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    search_fields = ("store_name", "user__username", "user__email", "user__phone_number")
    list_display = ("store_name", "user", "verification_status", "updated_at")
    list_filter = ("verification_status",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    search_fields = ("name", "brand", "seller__store_name")
    list_display = ("name", "brand", "seller", "approval_status", "created_at")
    list_filter = ("approval_status", "is_active")


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    search_fields = ("sku_code", "product__name")
    list_display = ("sku_code", "product", "selling_price", "stock_quantity", "is_active")
    list_filter = ("is_active",)


admin.site.register(ProductImage)
admin.site.register(Attribute)
admin.site.register(AttributeOption)
admin.site.register(VariantAttributeBridge)
admin.site.register(InventoryLog)
