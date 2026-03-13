from .models import Cart,CartItem,Wishlist,WishlistItem

def cart_count(request):
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            count = CartItem.objects.filter(cart=cart).count()
            return {"cart_count": count}

    return {"cart_count": 0}
def wishlist_count(request):
    if request.user.is_authenticated:
        count=WishlistItem.objects.filter(wishlist__user=request.user).count()
        return {"wishlist_count" : count }
    return {"wishlist_count": 0}