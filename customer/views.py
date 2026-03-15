from django.shortcuts import render,redirect,get_object_or_404
from core.models import *
from seller.models import *
from .models import *
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from core.decorator import customer_required

# Create your views here.
@login_required
def user_profile_view(request):
    user_obj =request.user
    if request.method=="POST":
        user_obj.first_name=request.POST.get("firstname")
        user_obj.last_name=request.POST.get("lastname")
        pro_image=request.FILES.get("profile_image")

        if pro_image:
            if user_obj.profile_image:
                user_obj.profile_image.delete(save=False)
            user_obj.profile_image=pro_image
        user_obj.save()
        messages.success(request,"Profile Updated Successfully.")
        return redirect("profile")
    addresses =Address.objects.filter(user=request.user)
    context={
        "addresses":addresses,
        "user":user_obj,
        }
    
    return render(request,"customer/profile.html",context)
@customer_required
def set_default_address(request,address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
    address.is_default = True
    address.save()
    messages.success(request, "Default address updated")
    return redirect("profile")
@customer_required
def delete_address(request,address_id):
    address =get_object_or_404(Address,user=request.user,id=address_id)
    address.delete()
    messages.error(request,"Address deleted successfully")
    return redirect("profile")

@customer_required
def save_address(request):

    if request.method == "POST":

        address_id = request.POST.get("address_id")

        full_name = request.POST.get("full_name")
        phone_number = request.POST.get("phone_number")
        pincode = request.POST.get("pincode")
        locality = request.POST.get("locality")
        house_info = request.POST.get("house_info")
        city = request.POST.get("city")
        state = request.POST.get("state")
        country = request.POST.get("country")
        landmark = request.POST.get("landmark")
        address_type = request.POST.get("address_type")
        is_default = request.POST.get("is_default") == "on"

        if address_id:
            address = get_object_or_404(Address, id=address_id, user=request.user)

        else:
            address = Address(user=request.user)

        address.full_name = full_name
        address.phone_number = phone_number
        address.pincode = pincode
        address.locality = locality
        address.house_info = house_info
        address.city = city
        address.state = state
        address.country = country
        address.landmark = landmark
        address.address_type = address_type
        address.is_default = is_default

        address.save()

        messages.success(request, "Address saved successfully")

    return redirect("profile")
    
@customer_required
def add_cart(request,variant_id):
    MAX_CART_QUANTITY = 3
    variant=get_object_or_404(
        ProductVariant.objects.select_related("product"),
        id=variant_id,product__is_active=True,
        product__approval_status="APPROVED"
    )
    if variant.stock_quantity < 1:
        return JsonResponse({'status':'error','message':'Out of Stock'},status=400)
    cart, created= Cart.objects.get_or_create(user=request.user)
    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={'price_at_time': variant.selling_price}
    )

    if not item_created:
        if cart_item.quantity >= MAX_CART_QUANTITY:
            return JsonResponse({
                'status': 'error',
                'message': 'Maximum 3 items allowed per product'
            }, status=400)
        if cart_item.quantity < variant.stock_quantity:
            cart_item.quantity += 1
            cart_item.save()
        else:
            return JsonResponse({'status': 'error', 'message': 'Stock limit reached'}, status=400)
    cart_count = cart.items.count()


    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'cart_count': cart_count
        })
    return redirect("product_details",slug=variant.product.slug)
@customer_required
def view_cart(request):
    cart,created=Cart.objects.get_or_create(user=request.user)
    cart_items = (
    CartItem.objects
    .select_related("variant","variant__product","variant__product__seller")
    .prefetch_related("variant__images",
        "variant__variant_attributes__option__attribute"
    )
    .filter(cart=cart))
    
    context = {
        "cart": cart,
        "cart_items": cart_items
    }

    return render(request, "customer/cart.html", context)
@customer_required
def delete_cart_item(request,cart_item_id):
    if request.method == "POST":
        cart_item =get_object_or_404(CartItem.objects.select_related("cart"),id=cart_item_id,cart__user=request.user) 
        cart_item.delete()
        messages.success(request, "Item removed from cart successfully.")
    return redirect("view_cart")



@customer_required
def update_cart_item(request):
    MAX_CART_QUANTITY = 3

    if request.method == "POST":

        item_id = request.POST.get("item_id")
        action = request.POST.get("action")

        cart_item = get_object_or_404(
            CartItem.objects.select_related("variant", "cart"),
            id=item_id,
            cart__user=request.user
        )

        if action == "increase":
            if cart_item.quantity >= MAX_CART_QUANTITY:
                   messages.error(request, "Maximum 3 items allowed per product.")
            elif cart_item.quantity >= cart_item.variant.stock_quantity:
                messages.error(request, "Stock limit reached.")
            else:
                cart_item.quantity += 1
                cart_item.save()
                messages.success(request, "Quantity increased")

        elif action == "decrease":

            cart_item.quantity -= 1

            if cart_item.quantity <= 0:
                cart_item.delete()
                messages.success(request, "Item removed from cart")
                return redirect("view_cart")

            cart_item.save()
            messages.success(request, "Quantity decreased")

    return redirect("view_cart")
@customer_required
def add_wishlist(request,variant_id):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)
    variant=get_object_or_404(ProductVariant,id=variant_id)
    wishlist = Wishlist.objects.filter(user=request.user,is_default=True).first()
    if not wishlist:
            wishlist,created=Wishlist.objects.get_or_create(
             user=request.user,
             wishlist_name="Mywishlist",
             is_default=True,
        )
    wishlist_item = WishlistItem.objects.filter(
        wishlist=wishlist,
        variant=variant
    ).first()
    if wishlist_item:
        wishlist_item.delete()
        return JsonResponse({
            "status":"removed"
        })
    else:
        WishlistItem.objects.create(
            wishlist=wishlist,
            variant=variant
        )
        return JsonResponse({
            "status":"added"
        })
@customer_required
def view_wishlist(request):

    collections = Wishlist.objects.filter(
        user=request.user
    ).prefetch_related(
        "items__variant__product",
        "items__variant__product__seller",
        "items__variant__images",

    )

    collection_id = request.GET.get("collection")

    active_collection = None
    wishlist_items = None

    if collection_id:
        active_collection = collections.filter(id=collection_id).first()

    if not active_collection:
        active_collection = collections.filter(is_default=True).first()
    if not active_collection:
        active_collection = collections.first()

    if active_collection:
        wishlist_items = active_collection.items.select_related(
            "variant__product",
            "variant__product__seller"
        )

    context = {
        "collections": collections,
        "wishlist_items": wishlist_items,
        "active_collection": active_collection,
    }

    return render(request, "customer/wishlist.html", context)
@customer_required
def add_collection(request):

    if request.method != "POST":
        return  redirect("view_wishlist")

    name = request.POST.get("name")

    collection, created = Wishlist.objects.get_or_create(
        user=request.user,
        wishlist_name=name
    )

    if not created:
      messages.error(request, "Collection already exists")
      return redirect("view_wishlist")
    if not Wishlist.objects.filter(user=request.user, is_default=True).exists():
        collection.is_default = True
        collection.save()

    messages.success(request, "Collection created successfully")
    return redirect("view_wishlist")
@customer_required
def set_default_collection(request,collection_id):
     if request.method != "POST":
        return redirect("view_wishlist")
     collection=get_object_or_404(Wishlist,id=collection_id,user=request.user)
     Wishlist.objects.filter(user=request.user,is_default=True).update(is_default=False)
     collection.is_default=True
     collection.save()
     return redirect("view_wishlist")
@customer_required
def remove_wishlist_item(request, item_id):

    if request.method != "POST":
        return redirect("view_wishlist")

    item = get_object_or_404(
        WishlistItem,
        id=item_id,
        wishlist__user=request.user
    )

    item.delete()
    messages.success(request, "product removed successfully")

    return redirect("view_wishlist")
@customer_required
def remove_collection(request, collection_id):

    if request.method != "POST":
        return redirect("view_wishlist")

    collection = get_object_or_404(
        Wishlist,
        id=collection_id,
        user=request.user
    )

    was_default = collection.is_default

    collection.delete()

    if was_default:
        new_default = Wishlist.objects.filter(
            user=request.user,
            is_default=False
        ).first()

        if new_default:
            new_default.is_default = True
            new_default.save(update_fields=["is_default"])

    messages.success(request, "Collection deleted successfully")

    return redirect("view_wishlist")





