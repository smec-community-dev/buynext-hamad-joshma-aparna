from django.contrib import admin
from .models import (
    Cart,
    CartItem,
    Wishlist,
    WishlistItem,
    Review,
    Order,
    OrderItem,
)

admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Wishlist)
admin.site.register(WishlistItem)
admin.site.register(Review)
admin.site.register(Order)
admin.site.register(OrderItem)
