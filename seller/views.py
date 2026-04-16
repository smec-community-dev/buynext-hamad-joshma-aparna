import os
import uuid
from django.shortcuts import render,redirect,get_object_or_404
from core.models import *
from .models import *
from bnadmin.models import *
from django.contrib import messages
from django.db.models import Prefetch
from django.contrib.auth import login,authenticate
from core.decorator import seller_profile_required,verified_seller_required
from django.db.models import Sum, Count, Q, F, Avg
from .models import SellerProfile, Product, ProductVariant, InventoryLog
from django.http import JsonResponse
from customer.models import Review, Order as CustomerOrder, OrderItem as CustomerOrderItem
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from datetime import timedelta
import json





def _variant_label(variant):
     bridges = list(variant.variant_attributes.all())
     if not bridges:
          return variant.sku_code or "Standard"
     values = [bridge.option.value for bridge in bridges]
     return " / ".join(values)


def _is_video_file(upload):
     content_type = getattr(upload, "content_type", "") or ""
     if content_type.startswith("video/"):
          return True
     ext = os.path.splitext(upload.name or "")[1].lower()
     return ext in {".mp4", ".mov", ".webm", ".ogg", ".m4v"}

def user_seller_bridge(request):
    return render(request,"seller/user_seller_bridge.html")


def seller_registration(request):
    if request.method == "POST":

        store_name = request.POST.get("store_name", "").strip()
        gst_number = request.POST.get("gst_number", "").strip()
        description = request.POST.get("description", "").strip()
        logo = request.FILES.get("logo")

        if SellerProfile.objects.filter(store_name__iexact=store_name).exists():
            messages.error(request, "Store name already exists")
            return render(request, "seller/seller_registration.html", {"data": request.POST})

        if SellerProfile.objects.filter(gst_number=gst_number).exists():
            messages.error(request, "GST already registered")
            return render(request, "seller/seller_registration.html", {"data": request.POST})

        if not request.user.is_authenticated:

            phone_number = request.POST.get("phone_number", "").strip()
            email = request.POST.get("email", "").strip().lower()
            print(email)
            print(phone_number)
            password = request.POST.get("password")
            confirm_password = request.POST.get("confirm_password")

            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            username_input = request.POST.get("username", "").strip()

            if password != confirm_password:
                messages.error(request, "Passwords do not match")
                return render(request, "seller/seller_registration.html", {"data": request.POST})

            if User.objects.filter(phone_number=phone_number).exists():
                messages.error(request, "Phone number already registered")
                return render(request, "seller/seller_registration.html", {"data": request.POST})

            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, "Email already registered")
                return render(request, "seller/seller_registration.html", {"data": request.POST})

            if username_input:
                if User.objects.filter(username__iexact=username_input).exists():
                    messages.error(request, "Username already taken")
                    return render(request, "seller/seller_registration.html", {"data": request.POST})
                username = username_input
            else:
                username = f"{email.split('@')[0]}_{uuid.uuid4().hex[:5]}"

            user = User.objects.create_user(
                username=username,
                phone_number=phone_number,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)

        else:
            user = request.user

        if hasattr(user, "seller_profile"):
            messages.warning(request, "You already have a seller account")
            return redirect("seller_profile")

        SellerProfile.objects.create(
            user=user,
            store_name=store_name,
            gst_number=gst_number,
            description=description,
            logo=logo,
            verification_status="PENDING"
        )
        if not user.is_email_verified:
            messages.warning(request, "Please verify your email")
            request.session["verify_user"] = user.id
            request.session["verify_source"] = "seller"
            return redirect("email_verification")

        return redirect("seller_profile")

    return render(request, "seller/seller_registration.html", {"data": request.POST})


@verified_seller_required
def seller_dashboard(request):

    seller = request.user.seller_profile

    total_products = Product.objects.filter(seller=seller).count()
    total_orders = CustomerOrderItem.objects.filter(
        Q(seller=seller)
        | Q(seller__isnull=True, variant__product__seller=seller)
    ).values("order_id").distinct().count()

    context = {
        "total_products": total_products,
        "total_orders": total_orders,
    }

    return render(request, "seller/dashboard.html", context)
    
    
@verified_seller_required
def seller_products(request):
     seller=request.user.seller_profile
     products = (
    Product.objects.filter(seller=seller).select_related("subcategory").prefetch_related(
        "gallery",
        "variants",
        "variants__images",
        "variants__variant_attributes__option__attribute",
        "rejection_reasons",
    ).order_by("-created_at")
)
     query=request.GET.get("q")
     if query:
          products = products.filter( Q(name__icontains=query) | Q(brand__icontains=query) | Q(variants__sku_code__icontains=query)).distinct()
     status = request.GET.get("status")

     if status == "active":
        products = products.filter(is_active=True)

     elif status == "inactive":
        products = products.filter(is_active=False)
     products_pending_count = products.filter(approval_status="PENDING").count()
     products_approved_count = products.filter(approval_status="APPROVED").count()
     products_rejected_count = products.filter(approval_status="REJECTED").count()
     for product in products:

        variants = product.variants.all()
        product.variant_count = variants.count()
        product.total_stock = sum(v.stock_quantity for v in variants)
        product.stock_percentage = min((product.total_stock / 100) * 100 if product.total_stock else 0,100)
        product.latest_rejection = product.rejection_reasons.first()
          
     return render(request,"seller/product.html",{"products": products,"products_pending_count": products_pending_count,
        "products_approved_count": products_approved_count,
        "products_rejected_count": products_rejected_count,})

        
@verified_seller_required
def deactivate_product(request, id):
    product = Product.objects.get(id=id, seller=request.user.seller_profile)
    product.is_active = False
    product.save()
    return redirect("seller_product")
@verified_seller_required
def activate_product(request, id):
    product = Product.objects.get(id=id, seller=request.user.seller_profile)
    product.is_active = True
    product.save()
    return redirect("seller_product")
@verified_seller_required
def deactivate_variant(request, id):
    variant = ProductVariant.objects.get(id=id)
    variant.is_active = False
    variant.save()
    return redirect("seller_product")
@verified_seller_required
def activate_variant(request, id):
    variant = ProductVariant.objects.get(id=id)
    variant.is_active = True
    variant.save()
    return redirect("seller_product")

@verified_seller_required
def add_products(request):
     subcategory =SubCategory.objects.all()
     if request.method == "POST":
        name = request.POST.get("name")
        brand = request.POST.get("brand")
        description = request.POST.get("description")
        model_number = request.POST.get("model_number")
        subcategory_id = request.POST.get("subcategory")
        is_cancellable = request.POST.get("is_cancellable") == "on"
        is_returnable = request.POST.get("is_returnable") == "on"
        return_days = request.POST.get("return_days") or 0
        status = request.POST.get("status")
        if status == "draft":
            approval_status = "DRAFT"
        else:
            approval_status = "PENDING"

        product = Product.objects.create(
            seller=request.user.seller_profile,
            name=name,
            brand=brand,
            description=description,
            model_number=model_number,
            subcategory_id=subcategory_id,
            is_cancellable=is_cancellable,
            is_returnable=is_returnable,
            return_days=return_days,
            approval_status=approval_status
        )
        images = request.FILES.getlist("product_images")
        images += request.FILES.getlist("product_images[]")
        try:
            primary_index = int(request.POST.get("primary_image_index", 0))
        except (TypeError, ValueError):
            primary_index = 0

        if images:
            if primary_index < 0 or primary_index >= len(images):
                primary_index = 0

            for index, image in enumerate(images):
                if _is_video_file(image):
                    ProductGallery.objects.create(
                        product=product,
                        video=image,
                        is_primary=(index == primary_index),
                        display_order=index,
                    )
                else:
                    ProductGallery.objects.create(
                        product=product,
                        image=image,
                        is_primary=(index == primary_index),
                        display_order=index,
                    )

        return redirect("product_status")
     return render(request,"seller/addproduct.html",{"subcategories":subcategory})

@verified_seller_required
def edit_product(request, product_id):

    product = get_object_or_404(
        Product,
        id=product_id,
        seller=request.user.seller_profile,
    )

    subcategories = SubCategory.objects.all()

    if request.method == "POST":

        product.name = request.POST.get("name")
        product.brand = request.POST.get("brand")
        product.description = request.POST.get("description")
        product.model_number = request.POST.get("model_number")
        product.subcategory_id = request.POST.get("subcategory")

        product.is_cancellable = request.POST.get("is_cancellable") == "on"
        product.is_returnable = request.POST.get("is_returnable") == "on"
        product.return_days = request.POST.get("return_days") or 0

        status = request.POST.get("status")

        if status == "draft":
            product.approval_status = "DRAFT"
        else:
            product.approval_status = "PENDING"

        product.save()

        images = request.FILES.getlist("product_images")

        if images:
            ProductGallery.objects.filter(product=product).delete()

            try:
                primary_index = int(request.POST.get("primary_image_index") or 0)
            except (TypeError, ValueError):
                primary_index = 0

            if primary_index < 0 or primary_index >= len(images):
                primary_index = 0

            for index, image in enumerate(images):
                if _is_video_file(image):
                    ProductGallery.objects.create(
                        product=product,
                        video=image,
                        is_primary=(index == primary_index),
                        display_order=index,
                    )
                else:
                    ProductGallery.objects.create(
                        product=product,
                        image=image,
                        is_primary=(index == primary_index),
                        display_order=index,
                    )

        if not ProductGallery.objects.filter(product=product, is_primary=True).exists():
            fallback = ProductGallery.objects.filter(product=product).order_by(
                "display_order", "created_at"
            ).first()
            if fallback:
                fallback.is_primary = True
                fallback.save(update_fields=["is_primary"])

        return redirect("product_status")

    return render(request, "seller/addproduct.html", {
        "product": product,
        "subcategories": subcategories
    })


@verified_seller_required
def add_variant(request,product_id):
     product =get_object_or_404(Product,id=product_id,seller=request.user.seller_profile)
     attributes=Attribute.objects.filter(subcategories=product.subcategory).prefetch_related("options").order_by("display_order")
     print(product.subcategory) 
     print(Attribute.objects.filter(subcategories=product.subcategory))
     if request.method == "POST":
        mrp = request.POST.get("MRP") or 0
        selling_price = request.POST.get("selling_price")
        cost_price = request.POST.get("cost_price") or 0
        stock = request.POST.get("stock") or 0
        low_stock_threshold = request.POST.get("low_stock_threshold") or 5
        if not selling_price:
            messages.error(request, "Selling price is required.")
            return redirect("add_variant", product_id=product.id)

        variant=ProductVariant.objects.create(
            product=product,
            selling_price=selling_price,
            mrp=mrp,  
            cost_price=cost_price,
            stock_quantity=stock,
            low_stock_threshold=low_stock_threshold

        )
        for attribute in attributes:
             option_id=request.POST.get(f"attribute_{attribute.id}")
             if option_id:
                  option=AttributeOption.objects.get(id=option_id)
                  VariantAttributeBridge.objects.create(
                       variant=variant,
                       option=option
                  )
        images = request.FILES.getlist("variant_images")
        for index,img in enumerate(images):
              ProductImage.objects.create(
                variant=variant,
                image=img,
                is_primary=(index == 0),
                display_order=index
            )
        messages.success(request, "Variant created successfully.")
        if request.POST.get("_add_another") == "true":
            return redirect("add_variant", product_id=product.id)
        return redirect("seller_product")
          
     return render(request,"seller/addvariant.html",{"product":product,"attributes":attributes})





@verified_seller_required
def seller_product_preview(request, product_id):
    product = get_object_or_404(
        Product,
        id=product_id,
        seller=request.user.seller_profile
    )

    variants = ProductVariant.objects.filter(product=product).prefetch_related(
        Prefetch('images', to_attr='product_images'),
        Prefetch(
            'variant_attributes',
            queryset=VariantAttributeBridge.objects.select_related('option__attribute'),
        )
    ).order_by('id')

    primary_variant = variants.first()

    gallery_images = []

    for variant in variants:
        for img in getattr(variant, 'product_images', []):
            if img.image:
                gallery_images.append({
                    "url": img.image.url,
                    "variant_id": str(variant.id),  
                    "is_primary": img.is_primary
                })

    context = {
        "product": product,
        "variants": variants,
        "primary_variant": primary_variant,
        "gallery_images": gallery_images,
    }

    return render(request, "seller/product_preview.html", context)


@verified_seller_required
def product_status(request):
     products = Product.objects.filter(seller=request.user.seller_profile)
     return render(request,"seller/product_status.html",{"products":products})

@verified_seller_required
def inventory_dashboard(request):

    variants = ProductVariant.objects.select_related('product').all()

    low_stock_items = variants.filter(stock__lte=5)

    recent_logs = InventoryLog.objects.select_related('variant')[:10]

    total_value = variants.aggregate(
        total=Sum(F('stock') * F('price'))
    )['total'] or 0

    context = {
        "variants": variants,
        "low_stock_count": low_stock_items.count(),
        "recent_logs": recent_logs,
        "total_value": total_value,
    }

    return render(request, "seller/inventory.html", context)

from django.db.models import F, Sum

@verified_seller_required
def seller_inventory(request):
    from django.db.models import Prefetch, F, Sum

    variants = ProductVariant.objects.select_related("product").prefetch_related(
        Prefetch("images", queryset=ProductImage.objects.order_by("-is_primary"))
    )

    low_stock_items = variants.filter(stock_quantity__lte=F("low_stock_threshold"))

    recent_logs = InventoryLog.objects.select_related("variant").order_by("-created_at")[:10]

    total_value = variants.aggregate(
        total=Sum(F("stock_quantity") * F("selling_price"))
    )["total"] or 0

    context = {
        "variants": variants,
        "low_stock_count": low_stock_items.count(),
        "recent_logs": recent_logs,
        "total_value": total_value,
    }

    return render(request, "seller/inventory.html", context)


@verified_seller_required
def adjust_inventory(request):
    if request.method == "POST":
        variant_id = request.POST.get("variant_id")
        adjustment_type = request.POST.get("adjustment_type")
        quantity = int(request.POST.get("quantity"))
        reason = request.POST.get("reason")

        variant = get_object_or_404(ProductVariant, id=variant_id)

        if adjustment_type == "add":
            change = quantity
            variant.stock_quantity += quantity

        elif adjustment_type == "remove":
            if quantity > variant.stock_quantity:
                messages.error(request, "Not enough stock")
                return redirect("seller_inventory")

            change = -quantity
            variant.stock_quantity -= quantity

        elif adjustment_type == "set":
            change = quantity - variant.stock_quantity
            variant.stock_quantity = quantity

        variant.save()

        InventoryLog.objects.create(
            variant=variant,
            change_amount=change,
            reason="ADJUSTMENT",
            note=reason
        )

        messages.success(request, "Inventory updated successfully")

    return redirect("seller_inventory")


@verified_seller_required
def seller_order(request):

    seller = request.user.seller_profile

    order_items = CustomerOrderItem.objects.filter(
        variant__product__seller=seller
    ).select_related(
        "order",
        "variant",
        "variant__product",
    )

    query = request.GET.get("q")
    if query:
        order_items = order_items.filter(
            Q(order__order_number__icontains=query) |
            Q(order__user__username__icontains=query)
        )

    status = request.GET.get("status")

    active_statuses = [
        "PLACED",
        "CONFIRMED",
        "PROCESSING",
        "SHIPPED",
        "OUT_FOR_DELIVERY",
    ]

    if status == "active":
        order_items = order_items.filter(item_status__in=active_statuses)

    elif status == "returns":
        order_items = order_items.filter(item_status="RETURN_REQUESTED")

    elif status == "cancelled":
        order_items = order_items.filter(item_status="CANCELLED")


    active_orders = CustomerOrderItem.objects.filter(
        variant__product__seller=seller,
        item_status__in=active_statuses
    ).values("order_id").distinct().count()


    returns_pending = CustomerOrderItem.objects.filter(
        variant__product__seller=seller,
        item_status="RETURN_REQUESTED"
    ).values("order_id").distinct().count()


    total_revenue = CustomerOrderItem.objects.filter(
        variant__product__seller=seller
    ).aggregate(
        total=Sum(F("price_at_purchase") * F("quantity"))
    )["total"] or 0


    context = {
        "active_orders": active_orders,
        "returns_pending": returns_pending,
        "total_revenue": total_revenue,
        "order_items": order_items,
    }

    return render(request, "seller/seller_order.html", context)



@verified_seller_required
def earnings_view(request):

    seller = request.user.seller_profile

    # ✅ FIXED QUERY
    order_items = OrderItem.objects.filter(
        seller=seller
    ).select_related("order", "variant")

    COMMISSION_RATE = Decimal("10.0")

    completed_items = order_items.filter(item_status="completed")

    gross_revenue = completed_items.aggregate(
        total=Sum (F("price_at_purchase") * F("quantity"))
    )["total"] or 0

    total_commission = completed_items.aggregate(
        total=Sum(
            F("price_at_purchase") * F("quantity") * (COMMISSION_RATE / 100)
        )
    )["total"] or 0

    total_net = gross_revenue - total_commission

    pending_items = completed_items.filter(
        order__updated_at__gte=now() - timedelta(days=7)
    )

    pending_settlement = pending_items.aggregate(
        total=Sum(F("price_at_purchase") * F("quantity"))
    )["total"] or 0

    settled_items = completed_items.filter(
        order__updated_at__lt=now() - timedelta(days=7)
    )

    settled_amount = settled_items.aggregate(
        total=Sum(
            (F("price_at_purchase")* F("quantity")) * (1 - COMMISSION_RATE / 100)
        )
    )["total"] or 0

    context = {
        "order_items": order_items,
        "total_commission": round(total_commission, 2),
        "total_net": round(total_net, 2),
        "pending_settlement": pending_settlement,
        "settled_amount": settled_amount,
        "commission_rate": COMMISSION_RATE,
    }

    return render(request, "seller/earnings.html", context)




@verified_seller_required
def offer_discount(request):
     return render(request,"seller/offeranddiscount.html")

@verified_seller_required
def seller_reviews(request):

    seller = request.user.seller_profile

    reviews = Review.objects.filter(
        product__seller=seller,
        is_approved=True
    ).select_related("product", "user")

    # attach seller reply to each review
    for review in reviews:
        review.seller_reply_obj = ReviewReply.objects.filter(
            review=review,
            seller=seller
        ).first()

    avg_rating = reviews.aggregate(Avg("rating"))["rating__avg"]

    rating_counts = reviews.values("rating").annotate(count=Count("rating"))

    context = {
        "reviews": reviews,
        "avg_rating": avg_rating,
        "rating_counts": rating_counts
    }

    return render(request, "seller/sellerreviews.html", context)


@verified_seller_required
def reply_review(request, review_id):

    review = get_object_or_404(
        Review,
        id=review_id,
        product__seller=request.user.seller_profile
    )

    if request.method == "POST":
        reply_text = request.POST.get("reply")

        ReviewReply.objects.update_or_create(
            review=review,
            seller=request.user.seller_profile,
            defaults={"reply": reply_text}
        )

    return redirect("seller_reviews")


@verified_seller_required
def delete_reply(request, review_id):

    review = get_object_or_404(
        Review,
        id=review_id,
        product__seller=request.user.seller_profile
    )

    reply = ReviewReply.objects.filter(
        review=review,
        seller=request.user.seller_profile
    ).first()

    if request.method == "POST" and reply:
        reply.delete()

    return redirect("seller_reviews")



from django.contrib import messages
from django.shortcuts import render, redirect
from seller.models import SellerProfile
from core.models import User

@seller_profile_required
def seller_profile(request):

    profile = request.user.seller_profile

    if request.method == "POST":

        store_name = (request.POST.get("store_name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        email = (request.POST.get("business_email") or "").strip().lower()
        phone = (request.POST.get("business_phone") or "").strip()
        if SellerProfile.objects.filter(store_name=store_name).exclude(user=request.user).exists():
            messages.error(request, "Store name already taken")
            return redirect("seller_profile")

        profile.store_name = store_name
        profile.description = description

        if request.FILES.get("logo"):
            if profile.logo:
                profile.logo.delete(save=False)
            profile.logo = request.FILES.get("logo")

        if request.FILES.get("banner"):
            if profile.banner:
                profile.banner.delete(save=False)
            profile.banner = request.FILES.get("banner")

        if email and email != request.user.email:
            if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                messages.error(request, "Email already in use")
                return redirect("seller_profile")


            request.user.email = email
            request.user.is_email_verified = False 
            request.user.save()

            messages.warning(request, "Please verify your new email")
            profile.save()

        if phone and phone != request.user.phone_number:
            if User.objects.filter(phone_number=phone).exclude(id=request.user.id).exists():
                messages.error(request, "Phone number already in use")
                return redirect("seller_profile")

            request.user.phone_number = phone
            request.user.is_phone_verified = False
            request.user.save()

            messages.warning(request, "Please verify your new phone number")

        profile.save()

        messages.success(request, "Profile updated successfully")

        return redirect("seller_profile") 

    return render(request, "seller/sellerprofile.html", {
        "profile": profile
    })
@verified_seller_required
def seller_settings(request):
     return render(request,"seller/seller_settings.html")


from django.core.mail import send_mail
from django.conf import settings

@verified_seller_required
def update_order_item_status(request, item_id):

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"})

    try:
        data = json.loads(request.body)
        status = (data.get("status") or "").strip().lower()

        status_map = {
            "placed": "PLACED",
            "confirmed": "CONFIRMED",
            "processing": "PROCESSING",
            "shipped": "SHIPPED",
            "out_for_delivery": "OUT_FOR_DELIVERY",
            "delivered": "DELIVERED",
            "cancelled": "CANCELLED",
            "return_requested": "RETURN_REQUESTED",
            "returned": "RETURNED",
        }

        if status not in status_map:
            return JsonResponse({"success": False, "error": "Invalid status"})

        item = get_object_or_404(CustomerOrderItem, id=item_id)

        if item.variant.product.seller != request.user.seller_profile:
            return JsonResponse({"success": False, "error": "Unauthorized"})

        if item.item_status in ["CANCELLED", "RETURNED"]:
            return JsonResponse({"success": False, "error": "Cannot update this item"})

        item.item_status = status_map[status]
        item.save(update_fields=["item_status"])

        # ✅ Send email
        send_status_email(item)

        return JsonResponse({"success": True, "message": "Item status updated"})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})
from django.core.mail import send_mail
from django.conf import settings

def send_status_email(item):
    order = item.order
    user = order.user

    readable_status = item.item_status.replace("_", " ").title()

    subject = f"Order Update - {order.order_number}"

    message = f"""
Hi {user.username},

Your order status has been updated.

Product: {item.variant}
Quantity: {item.quantity}

Current Status: {readable_status}

Thank you for shopping with us!

- BuyNext Team
"""

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=True,
    )


@verified_seller_required
def handle_return(request, item_id):

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"})

    action = (request.POST.get("action") or "").lower()

    if action not in ["approve", "reject"]:
        return JsonResponse({"success": False, "error": "Invalid action"})

    item = get_object_or_404(CustomerOrderItem, id=item_id)

    if item.variant.product.seller != request.user.seller_profile:
        return JsonResponse({"success": False, "error": "Unauthorized"})

    if item.item_status != "RETURN_REQUESTED":
        return JsonResponse({"success": False, "error": "Invalid state"})

    if action == "approve":
        item.item_status = "RETURNED"
    else:
        item.item_status = "DELIVERED"

    item.save(update_fields=["item_status"])

    return JsonResponse({
        "success": True,
        "message": f"Return {action}d successfully"
    })


from django.http import HttpResponse

@verified_seller_required
def seller_order_detail(request, order_id):

    seller = request.user.seller_profile

    items = CustomerOrderItem.objects.filter(
        order__order_number=order_id,
        variant__product__seller=seller
    ).select_related(
        "order",
        "order__user",
        "variant",
        "variant__product"
    )

    if not items.exists():
        return HttpResponse("No items found", status=404)

    order = items.first().order

    return render(request, "seller/order_detail.html", {
        "order": order,
        "items": items
    })

@verified_seller_required
def delete_reply(request, review_id):

    review = get_object_or_404(Review, id=review_id)

    reply = ReviewReply.objects.filter(
        review=review,
        seller=request.user.seller_profile
    ).first()

    if request.method == "POST" and reply:
        reply.delete()

    return redirect("seller_reviews")

@verified_seller_required
def reply_review(request, review_id):

    review = get_object_or_404(Review, id=review_id)

    if request.method == "POST":
        reply_text = request.POST.get("reply")

        ReviewReply.objects.update_or_create(
            review=review,
            seller=request.user.seller_profile,
            defaults={"reply": reply_text}
        )

    return redirect("seller_reviews")