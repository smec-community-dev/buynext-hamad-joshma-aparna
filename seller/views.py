import os
from django.shortcuts import render,redirect,get_object_or_404
from core.models import *
from .models import *
from bnadmin.models import *
from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Q, Prefetch
from core.decorator import seller_profile_required,verified_seller_required


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
     return render(request,"seller/dashboard.html")
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
def seller_product_preview(request, product_id):
     product = get_object_or_404(
          Product.objects.select_related(
               "seller",
               "seller__user",
               "subcategory",
               "subcategory__category",
          ).prefetch_related(
               "gallery",
               "rejection_reasons",
               Prefetch(
                    "variants",
                    queryset=ProductVariant.objects.prefetch_related(
                         "images",
                         "variant_attributes__option__attribute",
                    ).order_by("-is_active", "selling_price", "created_at"),
               ),
          ),
          id=product_id,
          seller=request.user.seller_profile,
     )

     variants = list(product.variants.all())
     primary_variant = next((variant for variant in variants if variant.is_active), None)
     if primary_variant is None and variants:
          primary_variant = variants[0]

     gallery_images = []
     seen_urls = set()

     for image in product.gallery.all():
          if image.video:
               media_url = image.video.url
               media_type = "video"
          elif image.image:
               media_url = image.image.url
               media_type = "image"
          else:
               continue
          if media_url in seen_urls:
               continue
          seen_urls.add(media_url)
          gallery_images.append(
               {
                    "url": media_url,
                    "alt": image.alt_text or product.name,
                    "type": media_type,
               }
          )

     if not gallery_images:
          for variant in variants:
               for image in variant.images.all():
                    if not image.image:
                         continue
                    image_url = image.image.url
                    if image_url in seen_urls:
                         continue
                    seen_urls.add(image_url)
                    gallery_images.append(
                         {
                              "url": image_url,
                              "alt": image.alt_text or product.name,
                              "type": "image",
                         }
                    )

     variant_cards = []
     for variant in variants:
          variant_cards.append(
               {
                    "id": str(variant.id),
                    "label": _variant_label(variant),
                    "attributes": [
                         {
                              "name": bridge.option.attribute.name,
                              "value": bridge.option.value,
                         }
                         for bridge in variant.variant_attributes.all()
                    ],
                    "sku": variant.sku_code,
                    "price": variant.selling_price,
                    "mrp": variant.mrp,
                    "stock_quantity": variant.stock_quantity,
                    "discount": variant.discount_percentage,
                    "is_active": variant.is_active,
                    "is_in_stock": variant.is_in_stock,
                    "image_url": next(
                         (image.image.url for image in variant.images.all() if image.image),
                         "",
                    ),
               }
          )

     context = {
          "product": product,
          "gallery_images": gallery_images,
          "variant_cards": variant_cards,
          "primary_variant": primary_variant,
          "latest_rejection": product.rejection_reasons.first(),
     }

     return render(request, "seller/product_preview.html", context)
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
     subcategory = SubCategory.objects.all()
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
        Product.objects.prefetch_related("gallery"),
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
            approval_status = "DRAFT"
        else:
            approval_status = "PENDING"


        product.approval_status = approval_status

        product.save()


        remove_gallery_ids = request.POST.getlist("remove_gallery_ids")
        existing_primary_id = request.POST.get("existing_primary_id", "").strip()

        if remove_gallery_ids:
            ProductGallery.objects.filter(
                product=product,
                id__in=remove_gallery_ids,
            ).delete()

        if existing_primary_id:
            if existing_primary_id in remove_gallery_ids:
                existing_primary_id = ""
            else:
                ProductGallery.objects.filter(product=product).update(is_primary=False)
                ProductGallery.objects.filter(
                    product=product,
                    id=existing_primary_id,
                ).update(is_primary=True)

        images = request.FILES.getlist("product_images")
        images += request.FILES.getlist("product_images[]")
        try:
            primary_index = int(request.POST.get("primary_image_index", 0))
        except (TypeError, ValueError):
            primary_index = 0

        existing_count = ProductGallery.objects.filter(product=product).count()
        has_primary = ProductGallery.objects.filter(
            product=product, is_primary=True
        ).exists()

        if images:
            if primary_index < 0 or primary_index >= len(images):
                primary_index = 0

            for index, image in enumerate(images):
                if _is_video_file(image):
                    ProductGallery.objects.create(
                        product=product,
                        video=image,
                        is_primary=(not has_primary and index == primary_index),
                        display_order=existing_count + index,
                    )
                else:
                    ProductGallery.objects.create(
                        product=product,
                        image=image,
                        is_primary=(not has_primary and index == primary_index),
                        display_order=existing_count + index,
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
def product_status(request):
     products = Product.objects.filter(seller=request.user.seller_profile).select_related("subcategory").prefetch_related("gallery", "rejection_reasons")
     products_pending_count = products.filter(approval_status="PENDING").count()
     products_approved_count = products.filter(approval_status="APPROVED").count()
     products_rejected_count = products.filter(approval_status="REJECTED").count()
     for product in products:
          product.latest_rejection = product.rejection_reasons.first()
     return render(request,"seller/product_status.html",{
          "products":products,
          "products_pending_count": products_pending_count,
          "products_approved_count": products_approved_count,
          "products_rejected_count": products_rejected_count,
     })
@verified_seller_required
def seller_inventory(request):
     return render(request,"seller/inventory.html")
@verified_seller_required
def seller_order(request):
     return render(request,"seller/seller_order.html")
@verified_seller_required
def seller_earnings(request):
     return render(request,"seller/earnings.html")
@verified_seller_required
def offer_discount(request):
     return render(request,"seller/offeranddiscount.html")
@verified_seller_required
def seller_reviews(request):
     return render(request,"seller/sellerreviews.html")
@seller_profile_required
def seller_profile(request):
    profile = request.user.seller_profile

    if request.method == "POST":
        profile.store_name = request.POST.get("store_name")
        profile.description = request.POST.get("description")

        if request.FILES.get("logo"):
            profile.logo = request.FILES.get("logo")

        if request.FILES.get("banner"):
            profile.banner = request.FILES.get("banner")

        profile.save()

    return render(request, "seller/sellerprofile.html", {
        "profile": profile
    })
@verified_seller_required
def seller_settings(request):
     return render(request,"seller/seller_settings.html")
