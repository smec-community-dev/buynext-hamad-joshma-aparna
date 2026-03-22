from django.shortcuts import render,redirect,get_object_or_404
from core.models import *
from .models import *
from bnadmin.models import *
from django.contrib import messages
from django.contrib.auth import login
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




# Create your views here.
def user_seller_bridge(request):
    return render(request,"seller/user_seller_bridge.html")
def seller_registration(request):
    if request.method == "POST":
         store_name=request.POST.get("store_name")
         gst_number=request.POST.get("gst_number")
         description=request.POST.get("description")
         logo=request.FILES.get("logo")
         if SellerProfile.objects.filter(store_name=store_name).exists():
               messages.error(request, "This store name is already registered. Please choose a unique brand name.")
               return render(request,"seller/seller_registration.html",{"data":request.POST})
         if SellerProfile.objects.filter(gst_number=gst_number).exists():
               messages.error(request, "This GSTIN is already linked to an existing seller account. Please log in to your original account.")
               return render(request,"seller/seller_registration.html",{"data":request.POST})    
         if not  request.user.is_authenticated:
              first_name=request.POST.get("first_name")
              last_name=request.POST.get("last_name")
              username=request.POST.get("username")
              email = request.POST.get("email")
              phone_no = request.POST.get("phone_display")
              password = request.POST.get("password")
              confirm_password = request.POST.get("confirm_password")
              if username:
                   final_username=username
              elif first_name or last_name:
                   final_username =(first_name+last_name).lower()
              elif email:
                   final_username = email.split("@")[0].lower()

              else:
                   final_username = "user"
                 
              if password != confirm_password:
                    messages.error(request, "Passwords do not match")
                    return render(request,"seller/seller_registration.html",{"data":request.POST})
              if User.objects.filter(username=final_username).exists():
                    messages.error(request, "Username already taken")
                    return render(request,"seller/seller_registration.html",{"data":request.POST})
              if User.objects.filter(email=email).exists():
                    messages.error(request, "Email already registered")
                    return render(request,"seller/seller_registration.html",{"data":request.POST})
              if User.objects.filter( phone_number=phone_no).exists():
                    messages.error(request, "phone number already registered")
                    return render(request,"seller/seller_registration.html",{"data":request.POST})
              user=User.objects.create_user(
                    username=final_username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone_number=phone_no,
                    password=password
                )
              user.is_active=True
              user.save()
              login(request, user)
         else:
              user=request.user
                
         seller_profile = SellerProfile.objects.create(
                user=user,
                store_name=store_name,
                gst_number = gst_number,
                description=description,
                logo=logo,
            )
         seller_profile.save()
         return redirect('seller_profile')
    return render(request,"seller/seller_registration.html",{"data":request.POST})


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
    Product.objects.filter(seller=seller).select_related("subcategory").prefetch_related("gallery","variants","variants__images","variants__variant_attributes__option__attribute").order_by("-created_at")
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
        images = request.FILES.getlist("product_images[]")

        primary_index = int(request.POST.get("primary_image_index", 0))

        for index, image in enumerate(images):

         ProductGallery.objects.create(
        product=product,
        image=image,
        is_primary=(index == primary_index),
        display_order=index
    )
         return redirect("product_status")
     return render(request,"seller/addproduct.html",{"subcategories":subcategory})

@verified_seller_required
def edit_product(request, product_id):

    product = get_object_or_404(
        Product,
        id=product_id,
        seller=request.user.seller_profile
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

            primary_index = int(request.POST.get("primary_image_index") or 0)

            for index, image in enumerate(images):

                ProductGallery.objects.create(
                    product=product,
                    image=image,
                    is_primary=(index == primary_index),
                    display_order=index
                )

        return redirect("product_status")

    return render(request, "seller/addproduct.html", {
        "product": product,
        "subcategories": subcategories
    })
def seller_product_preview(request, id):
   
    return render(request, "seller/product_preview.html", {"product": product})


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

def seller_product_preview(request, product_id):

    product = get_object_or_404(Product, id=product_id)

    variants = ProductVariant.objects.filter(product=product)

    gallery_images = ProductImage.objects.filter(variant__in=variants)

    primary_variant = variants.first()

    variant_cards = variants

    return render(request, "seller/product_preview.html", {
        "product": product,
        "gallery_images": gallery_images,
        "primary_variant": primary_variant,
        "variant_cards": variant_cards
    })


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    gallery_images = product.images.all()  

    if request.method == "POST" and request.FILES.getlist("product_images"):
        for img_file in request.FILES.getlist("product_images"):
            ProductImage.objects.create(product=product, image=img_file)
        return redirect('product_detail', product_id=product.id)

    context = {
        'product': product,
        'gallery_images': gallery_images,
      
    }
    return render(request, "seller/product_detail.html", context)

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
    variants = ProductVariant.objects.select_related("product").all()
    low_stock_items = variants.filter(stock_quantity__lte=F("low_stock_threshold"))
    recent_logs = InventoryLog.objects.select_related("variant").order_by("-created_at")[:10]
    total_value = variants.aggregate(
        total=Sum(F("stock_quantity") * F("selling_price")))["total"] or 0

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
            change = -quantity
            variant.stock_quantity -= quantity

        elif adjustment_type == "set":
            change = quantity - variant.stock
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

    order_items = OrderItem.objects.filter(
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
        order_items = order_items.filter(order__order_status__in=active_statuses)

    elif status == "returns":
        order_items = order_items.filter(order__order_status="RETURN_REQUESTED")

    elif status == "cancelled":
        order_items = order_items.filter(order__order_status="CANCELLED")


    active_orders = OrderItem.objects.filter(
        variant__product__seller=seller,
        order__order_status__in=active_statuses
    ).values("order_id").distinct().count()


    returns_pending = OrderItem.objects.filter(
        variant__product__seller=seller,
        order__order_status="RETURN_REQUESTED"
    ).values("order_id").distinct().count()


    total_revenue = OrderItem.objects.filter(
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

    
    avg_rating = Review.objects.filter(
        product__seller=seller
    ).aggregate(Avg("rating"))["rating__avg"]

    
    rating_counts = Review.objects.filter(
        product__seller=seller
    ).values("rating").annotate(count=Count("rating"))

    context = {
        "reviews": reviews,
        "avg_rating": avg_rating,
        "rating_counts": rating_counts
    }

    return render(request, "seller/sellerreviews.html", context)


@verified_seller_required
def reply_review(request, review_id):

    review = Review.objects.get(id=review_id)

    if request.method == "POST":

        reply = request.POST.get("reply")

        ReviewReply.objects.create(
            review=review,
            seller=request.user.seller_profile,
            reply=reply
        )

    return redirect("seller_reviews")



@seller_profile_required
def seller_profile(request):
    profile = request.user.seller_profile

    if request.method == "POST":
        profile.store_name = request.POST.get("store_name")
        profile.description = request.POST.get("description")

        if request.FILES.get("logo"):
            if profile.logo:
                   profile.logo.delete(save=False)
            profile.logo = request.FILES.get("logo")

        if request.FILES.get("banner"):
            if profile.banner:
                  profile.banner.delete(save=False)
            profile.banner = request.FILES.get("banner")

        profile.save()

    return render(request, "seller/sellerprofile.html", {
        "profile": profile
    })
@verified_seller_required
def seller_settings(request):
     return render(request,"seller/seller_settings.html")


@verified_seller_required
def update_order_status(request, order_id):

    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "error": "Invalid request method"
        })

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
            "refunded": "REFUNDED",
        }

        if status not in status_map:
            return JsonResponse({
                "success": False,
                "error": "Invalid status"
            })

    
        order = get_object_or_404(CustomerOrder, order_number=order_id)

        seller = request.user.seller_profile

     
        has_items = OrderItem.objects.filter(
            order=order,
            variant__product__seller=seller
        ).exists()

        if not has_items:
            return JsonResponse({
                "success": False,
                "error": "Not authorized for this order"
            })

       
        order.order_status = status_map[status]
        order.save(update_fields=["order_status"])

        return JsonResponse({
            "success": True,
            "message": "Order status updated successfully"
        })

    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "error": "Invalid JSON data"
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })