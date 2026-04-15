from django.shortcuts import render,redirect,get_object_or_404
from django.core.mail import send_mail
from twilio.rest import Client
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random
from .models import *
from seller.models import *
from seller.models import ProductVariant
from customer.models import * 
from django.db.models import Avg, Prefetch,Min,Max,Value,Count,Case,When,Q
from django.db.models.functions import Coalesce
from django.contrib.auth import authenticate,login,logout
from django.contrib import messages
from django.db.models import Q,F
from django.urls import reverse
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils.html import mark_safe
import re
from .trending import get_trending_products
from .decorator import _dashboard_for_user,admin_not_required
# Create your views here.

def login_view(request):
    if request.method == "POST":
        username_or_email = request.POST.get("username_or_email")
        password = request.POST.get("password")

        try:
            user_obj = User.objects.get(email=username_or_email)
            username = user_obj.username
        except User.DoesNotExist:
            username = username_or_email

        user = authenticate(request, username=username, password=password)

        if user is not None:
            is_admin_user = user.is_superuser or user.is_staff or getattr(user, "is_admin_role", False)

            if not is_admin_user and not (user.is_email_verified or user.is_phone_verified):
                messages.error(request, "Please verify your account first.")
                request.session["verify_user"] = user.id
                request.session["verify_source"] = "user"
                return redirect("choose_verification")

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            url = _dashboard_for_user(request.user, request)
            if url:
                return redirect(url)

            return redirect("home")

        else:
            messages.error(request, "Invalid credentials")

    return render(request, "core/login.html")


def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        phone_no = request.POST.get("full_phone")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request, "core/register.html")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken")
            return render(request, "core/register.html")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered")
            return render(request, "core/register.html")

        if User.objects.filter(phone_number=phone_no).exists():
            messages.error(request, "Phone number already registered")
            return render(request, "core/register.html")

        user = User.objects.create_user(
            username=username,
            email=email,
            phone_number=phone_no,
            password=password
        )
        user.save()

        request.session["verify_user"] = user.id
        request.session["verify_source"] = "user" 

        return redirect("choose_verification")

    return render(request, "core/register.html")
def choose_verification(request):
    user_id = request.session.get("verify_user")

    if not user_id:
        return redirect("register")

    if request.method == "POST":

        method = request.POST.get("method")

        if method == "email":
            return redirect("email_verification")

        if method == "phone":
            return redirect("phone_verification")

    return render(request, "core/choose_verification.html")


def email_verification(request):

    user_id = request.session.get("verify_user")

    if user_id:
        user = get_object_or_404(User, id=user_id)
    else:
        if request.user.is_authenticated:
            user = request.user
        else:
            return redirect("login")

    otp = str(random.randint(100000, 999999))

    OTPVerification.objects.filter(user=user).delete()

    OTPVerification.objects.create(user=user, otp=otp, method="email")

    try:
        send_mail(
            "BuyNext Verification OTP",
            f"Your OTP is {otp}",
            settings.EMAIL_HOST_USER,
            [user.email]
        )
    except Exception as e:
        print("EMAIL ERROR:", e)
        messages.error(request, "Failed to send email")
        return redirect("verify_otp")

    messages.success(request, "OTP sent to your email")

    return redirect("verify_otp")

def phone_verification(request):

    user_id = request.session.get("verify_user")
    if user_id:
        user = get_object_or_404(User, id=user_id)
    else:
        if request.user.is_authenticated:
            user = request.user
        else:
            return redirect("login")

    last_otp = OTPVerification.objects.filter(user=user).last()

    if last_otp and timezone.now() < last_otp.created_at + timedelta(seconds=30):
        messages.info(request, "Please wait before requesting another OTP")
        return redirect("verify_otp")

    otp = str(random.randint(100000, 999999))

    OTPVerification.objects.filter(user=user).delete()

    OTPVerification.objects.create(
        user=user,
        otp=otp,
        method="phone"
    )

    phone = user.phone_number
    if not phone or not str(phone).strip():
        messages.error(request, "Please add a phone number to your profile before verifying.")
        if request.user.is_authenticated:
            return redirect("profile")
        return redirect("choose_verification")

    phone = str(phone).strip()
    if not phone.startswith("+"):
        phone = f"+91{phone}"

    try:
        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )

        message = client.messages.create(
            body=f"Your BuyNext OTP is {otp}",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone
        )

        print("Twilio SID:", message.sid)

        messages.success(request, "OTP sent to your phone")

    except Exception as e:
        print("Twilio Error:", e)
        messages.error(request, "Failed to send OTP")

    return redirect("verify_otp")

def resend_otp(request):

    user_id = request.session.get("verify_user")

    if user_id:
        user = User.objects.get(id=user_id)
    else:
        if request.user.is_authenticated:
            user = request.user
        else:
            return redirect("login")

    last_otp = OTPVerification.objects.filter(user=user).last()

    if not last_otp:
        return redirect("choose_verification")

    if last_otp.method == "email":
        return redirect("email_verification")

    elif last_otp.method == "phone":
        return redirect("phone_verification")

    return redirect("verify_otp")


def verify_otp(request):

    user_id = request.session.get("verify_user")

    if user_id:
        user = User.objects.get(id=user_id)
    else:
        if request.user.is_authenticated:
            user = request.user
        else:
            return redirect("login")

    if request.method == "POST":

        otp = request.POST.get("otp")

        record = OTPVerification.objects.filter(user=user, otp=otp).last()

        if not record:
            messages.error(request, "Invalid OTP")
            return redirect("verify_otp")

        if record.is_expired():
            record.delete()
            messages.error(request, "OTP expired")
            return redirect("choose_verification")

        if record.method == "email":
            user.is_email_verified = True
        else:
            user.is_phone_verified = True

        user.save()
        record.delete()

        verify_source = request.session.get("verify_source")

        request.session.pop("verify_user", None)
        request.session.pop("verify_source", None)

        messages.success(request, "Verification successful.")

        if verify_source == "seller":
            return redirect("seller_profile")

        elif verify_source == "user":
            return redirect("profile")

        if request.user.is_authenticated:
            if request.user.is_seller:
                return redirect("seller_profile")
            return redirect("profile")

        return redirect("login")

    return render(request, "core/verify_otp.html")


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")

        user = User.objects.filter(email=email).first()

        if not user:
            messages.error(request, "Email not registered")
            return redirect("forgot_password")


        request.session["reset_user"] = user.id

        otp = str(random.randint(100000, 999999))

        OTPVerification.objects.filter(user=user).delete()

        OTPVerification.objects.create(
            user=user,
            otp=otp,
            method="email"
        )

        send_mail(
            "Password Reset OTP",
            f"Your OTP is {otp}",
            settings.EMAIL_HOST_USER,
            [user.email]
        )

        return redirect("verify_reset_otp")

    return render(request, "core/auth/forgot_password.html")


def verify_reset_otp(request):
    user_id = request.session.get("reset_user")

    if not user_id:
        return redirect("forgot_password")

    user = User.objects.get(id=user_id)

    if request.method == "POST":
        otp = request.POST.get("otp")

        record = OTPVerification.objects.filter(user=user, otp=otp).last()

        if not record:
            messages.error(request, "Invalid OTP")
            return redirect("verify_reset_otp")

        if record.is_expired():
            record.delete()
            messages.error(request, "OTP expired")
            return redirect("forgot_password")

        record.delete()

        request.session["reset_verified"] = True

        return redirect("reset_password")

    return render(request, "core/auth/verify_reset_otp.html")

def reset_password(request):
    user_id = request.session.get("reset_user")
    verified = request.session.get("reset_verified")

    if not user_id or not verified:
        return redirect("forgot_password")

    user = User.objects.get(id=user_id)

    if request.method == "POST":
        password = request.POST.get("password")
        confirm = request.POST.get("confirm_password")

        if password != confirm:
            messages.error(request, "Passwords do not match")
            return redirect("reset_password")

        user.set_password(password)
        user.save()


        request.session.pop("reset_user", None)
        request.session.pop("reset_verified", None)

        messages.success(request, "Password reset successful")
        return redirect("login")

    return render(request, "core/auth/reset_password.html")


@admin_not_required
def home_view(request):
    show_all = request.GET.get('show_all', False)

    categories = Category.objects.filter(
        is_active=True
    ).order_by('display_order', 'name')

    if not show_all:
        categories = categories[:10]

    from django.utils import timezone
    now = timezone.now()

    banners = Banner.objects.filter(
        is_active=True,
        start_date__lte=now,
        end_date__gte=now
    ).order_by('-created_at')[:5]

    trending_product = None
    trending_data = get_trending_products(days=30, limit=1)

    if trending_data:
        trending_product_id = trending_data[0]['variant__product']

        trending_product = Product.objects.filter(
            id=trending_product_id,
            is_active=True,
            approval_status='APPROVED'
        ).select_related(
            'seller', 'subcategory'
        ).prefetch_related(
            'gallery'
        ).first()

        if trending_product:
            img = trending_product.gallery.filter(is_primary=True).first()
            trending_product.primary_image = img.image.url if img else None

            variant = ProductVariant.objects.filter(
                product=trending_product,
                is_active=True
            ).first()

            trending_product.variant_id = variant.id if variant else None
            trending_product.min_price = variant.selling_price if variant else 0

            if request.user.is_authenticated and variant:
                trending_product.is_in_wishlist = WishlistItem.objects.filter(
                    wishlist__user=request.user,
                    variant=variant
                ).exists()
            else:
                trending_product.is_in_wishlist = False

    newest_products = Product.objects.filter(
        is_active=True,
        approval_status='APPROVED'
    ).select_related(
        'seller', 'subcategory', 'subcategory__category'
    ).prefetch_related(
        'gallery'
    ).order_by('-created_at')[:5]

    for product in newest_products:

        img = product.gallery.filter(is_primary=True).first()
        product.primary_image = img.image.url if img else None


        variant = ProductVariant.objects.filter(
            product=product,
            is_active=True
        ).first()

        product.variant_id = variant.id if variant else None
        product.min_price = variant.selling_price if variant else 0

        product.category_name = (
            product.subcategory.category.name
            if product.subcategory and product.subcategory.category
            else 'General'
        )

        if request.user.is_authenticated and variant:
            product.is_in_wishlist = WishlistItem.objects.filter(
                wishlist__user=request.user,
                variant=variant
            ).exists()
        else:
            product.is_in_wishlist = False


    context = {
        'categories': categories,
        'show_all': show_all,
        'total_categories': Category.objects.filter(is_active=True).count(),
        'banners': banners,
        'trending_product': trending_product,
        'newest_products': newest_products,
    }

    return render(request, "core/home.html", context)
@login_required
def logout_view(request):
    logout(request)
    return redirect("/")


@admin_not_required
def search_suggestions(request):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({"results": []})

    products = Product.objects.filter(
        is_active=True,
        approval_status="APPROVED"
    ).filter(
        Q(name__icontains=query) |
        Q(subcategory__name__icontains=query) |
        Q(seller__store_name__icontains=query)
    ).select_related("subcategory", "seller").prefetch_related("gallery")[:6]

    results = []

    for product in products:
        img = product.gallery.filter(is_primary=True).first()

        results.append({
            "name": product.name,
            "url": f"{reverse('all_products')}?q={product.name}",
            "image_url": img.image.url if img else "",
            "category": product.subcategory.name if product.subcategory else ""
        })

    return JsonResponse({"results": results})


@admin_not_required
def all_products(request):
    q = request.GET.get("q","").strip()
    categories = Category.objects.filter(is_active=True).order_by("display_order")

    selected_ids = request.GET.getlist("categories")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    sort_by = request.GET.get("sort", "newest")
    in_stock = request.GET.get("in_stock") == "1"
    products = Product.objects.filter(
        is_active=True,
        approval_status="APPROVED"
    )
    if q:
       pattern = re.compile(re.escape(q), re.IGNORECASE)
       for product in products:
            product.name = mark_safe(
                pattern.sub(
                    lambda m: f'<span class="bg-yellow-200 px-1 rounded">{m.group()}</span>',
                    product.name
                )
            )


    if q:
        products = products.filter(
        Q(name__icontains=q) |
        Q(description__icontains=q) |
        Q(subcategory__name__icontains=q) |
        Q(seller__store_name__icontains=q)
    ).distinct()
   
    if selected_ids:
        products = products.filter(subcategory__category__id__in=selected_ids)

    
    products = products.annotate(
    min_selling_price=Min("variants__selling_price"),
    min_mrp=Min("variants__mrp"),
    average_rating=Coalesce(
        Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
        Value(0.0)
    ),
    save_price=Min("variants__mrp") - Min("variants__selling_price")
)

    
    if min_price:
        try:
            products = products.filter(min_selling_price__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            products = products.filter(min_selling_price__lte=float(max_price))
        except ValueError:
            pass

    
    if in_stock:
        products = products.filter(variants__stock_quantity__gt=0)

    if sort_by == "price_low_high":
        products = products.order_by("min_selling_price")

    elif sort_by == "price_high_low":
        products = products.order_by("-min_selling_price")

    else:
        products = products.order_by("-created_at")

    products = products.select_related(
        "seller",
        "subcategory"
    ).prefetch_related(
        "variants",
        "gallery"
    ).distinct()

    for product in products:

       
        img = product.gallery.filter(is_primary=True).first()
        product.primary_image = img.image if img else None
       
        variant = product.variants.first()
        product.variant_id = variant.id if variant else None
        product.stock_quantity = variant.stock_quantity if variant else 0


        if request.user.is_authenticated and variant:
            product.is_in_wishlist = WishlistItem.objects.filter(
                wishlist__user=request.user,
                variant=variant
            ).exists()
        else:
            product.is_in_wishlist = False

   
    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    products = paginator.get_page(page_number)
    for product in products:
        product.review_count = Review.objects.filter(
            product=product,
            is_approved=True
        ).count()


    context = {
        "products": products,
        "categories": categories,
        "selected_categories": selected_ids,
        "sort_by": sort_by,
        "min_price": min_price,
        "max_price": max_price,
        "in_stock": in_stock,
        "search_query": q,
        "is_search": bool(q),
        "results_count": products.paginator.count if hasattr(products, "paginator") else len(products),
    }

    return render(request, "core/all_products.html", context)


@admin_not_required
def category_view(request, category_slug):

    active_category = get_object_or_404(
        Category,
        slug=category_slug,
        is_active=True
    )

    all_categories = Category.objects.filter(
        is_active=True
    ).order_by("display_order", "name")

    subcategories = active_category.subcategories.filter(
        is_active=True
    ).order_by("display_order", "name")

    selected_slug = request.GET.get("subcategory")
    selected_subcategory = None

    if selected_slug:
        selected_subcategory = subcategories.filter(slug=selected_slug).first()

    sort = request.GET.get("sort", "newest")

    products = Product.objects.filter(
        is_active=True,
        approval_status="APPROVED",
        subcategory__category=active_category
    ).select_related(
        "seller",
        "subcategory",
        "subcategory__category"
    ).prefetch_related(
        "variants",
        "variants__images",
        "gallery"
    )

    if selected_subcategory:
        products = products.filter(subcategory=selected_subcategory)

    products = products.annotate(
        min_selling_price=Min("variants__selling_price"),
        min_mrp=Min("variants__mrp"),            
        stock_quantity=Max("variants__stock_quantity"),
        average_rating=Coalesce(Avg("reviews__rating", filter=Q(reviews__is_approved=True)), Value(0.0))
    ,save_price=Min("variants__mrp") - Min("variants__selling_price"))
    rating_filter = request.GET.get("rating")
   
    if rating_filter:
        products = products.filter(average_rating__gte=float(rating_filter))

   
    if sort == "price_low_high":
        products = products.order_by("min_selling_price")

    elif sort == "price_high_low":
        products = products.order_by("-min_selling_price")

    else:
        products = products.order_by("-created_at")

 
    for product in products:
        variant = product.variants.filter(is_active=True, stock_quantity__gt=0).first()

        if not variant:
            variant = product.variants.filter(is_active=True).first()
        product.variant_id = variant.id if variant else None
        
        gallery = product.gallery.first()

        if gallery:
            product.primary_image = gallery.image
        else:
            
            if variant and variant.images.first():
                product.primary_image = variant.images.first().image
            else:
                product.primary_image = None
                
       
        if request.user.is_authenticated and variant:
            product.is_in_wishlist = WishlistItem.objects.filter(
                wishlist__user=request.user,
                variant=variant
            ).exists()
        else:
            product.is_in_wishlist = False
      
        product.review_count = Review.objects.filter(
            product=product,
            is_approved=True
        ).count()
    paginator = Paginator(products, 12) 
    page_number = request.GET.get("page")
    products = paginator.get_page(page_number)

    context = {
        "all_categories": all_categories,
        "active_category": active_category,
        "subcategories": subcategories,
        "selected_subcategory": selected_subcategory,
        "products": products,
        "sort": sort,
    }

    return render(request, "core/subcategory.html", context)

@admin_not_required
def subcategory_view(request, subcategory_slug):

    selected_subcategory = get_object_or_404(
        SubCategory,
        slug=subcategory_slug,
        is_active=True
    )

    active_category = selected_subcategory.category

    all_categories = Category.objects.filter(
        is_active=True
    ).order_by("display_order", "name")

    subcategories = active_category.subcategories.filter(
        is_active=True
    ).order_by("display_order", "name")

    sort = request.GET.get("sort", "newest")

    products = Product.objects.filter(
        is_active=True,
        approval_status="APPROVED",
        subcategory=selected_subcategory   # ✅ MAIN DIFFERENCE
    ).select_related(
        "seller",
        "subcategory",
        "subcategory__category"
    ).prefetch_related(
        "variants",
        "variants__images",
        "gallery"
    )

 
    products = products.annotate(
        min_selling_price=Min("variants__selling_price"),
        min_mrp=Min("variants__mrp"),
        stock_quantity=Max("variants__stock_quantity"),
        average_rating=Coalesce(
            Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
            Value(0.0)
        ),
        save_price=Min("variants__mrp") - Min("variants__selling_price")
    )

    rating_filter = request.GET.get("rating")

    if rating_filter:
        products = products.filter(average_rating__gte=float(rating_filter))

 
    if sort == "price_low_high":
        products = products.order_by("min_selling_price")
    elif sort == "price_high_low":
        products = products.order_by("-min_selling_price")
    else:
        products = products.order_by("-created_at")

    for product in products:
        variant = product.variants.filter(is_active=True, stock_quantity__gt=0).first()

        if not variant:
            variant = product.variants.filter(is_active=True).first()

        product.variant_id = variant.id if variant else None

        gallery = product.gallery.first()

        if gallery:
            product.primary_image = gallery.image
        else:
            if variant and variant.images.first():
                product.primary_image = variant.images.first().image
            else:
                product.primary_image = None

        if request.user.is_authenticated and variant:
            product.is_in_wishlist = WishlistItem.objects.filter(
                wishlist__user=request.user,
                variant=variant
            ).exists()
        else:
            product.is_in_wishlist = False

        product.review_count = Review.objects.filter(
            product=product,
            is_approved=True
        ).count()

    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    products = paginator.get_page(page_number)

    context = {
        "all_categories": all_categories,
        "active_category": active_category,
        "subcategories": subcategories,
        "selected_subcategory": selected_subcategory,  
        "products": products,
        "sort": sort,
    }

    return render(request, "core/subcategory.html", context)

@admin_not_required
def product_detail(request, slug):

    product = get_object_or_404(
        Product.objects.select_related(
            "seller",
            "subcategory",
            "subcategory__category"
        ),
        slug=slug,
        is_active=True,
        approval_status="APPROVED"
    )

    variants = ProductVariant.objects.filter(
        product=product,
        is_active=True
    ).prefetch_related(
        Prefetch(
            "images",
            queryset=ProductImage.objects.order_by("-is_primary", "display_order")
        ),
        Prefetch(
            "variant_attributes",
            queryset=VariantAttributeBridge.objects.select_related("option__attribute")
        ),
        'wishlist_items'
    )

    gallery_images = ProductGallery.objects.filter(product=product)

    default_variant = variants.filter(stock_quantity__gt=0).first() or variants.first()

    if default_variant:
        if request.user.is_authenticated:
            default_variant.is_in_wishlist = default_variant.wishlist_items.filter(
                wishlist__user=request.user
            ).exists()
        else:
            default_variant.is_in_wishlist = False

 
    reviews = Review.objects.filter(
        product=product,
        is_approved=True
    ).select_related("user").prefetch_related(
        Prefetch(
            "replies",
            queryset=ReviewReply.objects.select_related("seller").order_by("-created_at")
        )
    ).order_by("-created_at")

    rating_data = reviews.aggregate(avg=Avg("rating"))
    average_rating = round(rating_data["avg"] or 0, 1)
    review_count = reviews.count()

    user_has_reviewed = False
    user_review = None
    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()
        user_has_reviewed = user_review is not None

   
    similar_products = Product.objects.filter(
    subcategory=product.subcategory,
    is_active=True,
    approval_status="APPROVED"
).exclude(id=product.id).annotate(
    average_rating=Coalesce(
        Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
        Value(0.0)
    )
)[:8]

    context = {
        "product": product,
        "variants": variants,
        "gallery_images": gallery_images,
        "default_variant": default_variant,
        "reviews": reviews,
        "average_rating": average_rating,
        "review_count": review_count,
        "user_has_reviewed": user_has_reviewed,
        "user_review": user_review,
        "similar_products": similar_products, 
    }

    return render(request, "core/product_detail.html", context)



@admin_not_required
def new_arrivals(request):

    sort = request.GET.get("sort", "newest")
    category_slug = request.GET.get("category")
    rating_filter = request.GET.get("rating")
    in_stock = request.GET.get("in_stock")

    products = Product.objects.filter(
        is_active=True,
        approval_status="APPROVED"
    )

    if category_slug:
        products = products.filter(subcategory__category__slug=category_slug)

    products = products.annotate(
        min_selling_price=Min("variants__selling_price"),
        min_mrp=Min("variants__mrp"),
        total_stock=Max("variants__stock_quantity"),
        avg_rating=Coalesce(
            Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
            Value(0.0)
        ),
        save_amount=F("min_mrp") - F("min_selling_price")
    )
    if rating_filter:
        products = products.filter(avg_rating__gte=float(rating_filter))

    if in_stock:
        products = products.filter(total_stock__gt=0)

    if sort == "price_low":
        products = products.order_by("min_selling_price")
    elif sort == "price_high":
        products = products.order_by("-min_selling_price")
    elif sort == "rating":
        products = products.order_by("-avg_rating")
    else:
        products = products.order_by("-created_at")  

    products = products.select_related(
        "seller", "subcategory"
    ).prefetch_related(
        "variants", "gallery"
    ).distinct()

    for product in products:
        variant = product.variants.first()

        product.variant_id = variant.id if variant else None
        product.total_stock = variant.stock_quantity if variant else 0


        if product.min_mrp and product.min_selling_price and product.min_mrp > 0:
            product.discount_percent = round(
        ((product.min_mrp - product.min_selling_price) / product.min_mrp) * 100
    )
        else:
           product.discount_percent = 0

        if request.user.is_authenticated and variant:
            product.is_in_wishlist = WishlistItem.objects.filter(
                wishlist__user=request.user,
                variant=variant
            ).exists()
        else:
            product.is_in_wishlist = False

    seven_days_ago = timezone.now() - timedelta(days=7)

    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    products = paginator.get_page(page_number)

    context = {
        "products": products,
        "categories": Category.objects.filter(is_active=True),
        "current_sort": sort,
        "seven_days_ago": seven_days_ago,
         "is_newest_active": (sort == "newest" and not in_stock),
    }

    return render(request, "core/new_arrivals.html", context)

@admin_not_required
def trending_products_page(request):

    trending_raw = get_trending_products(days=7, limit=50)

    trending_products = []

    if trending_raw:

        product_ids = [item['variant__product'] for item in trending_raw]
        trending_variants = ProductVariant.objects.filter(
            product__id__in=product_ids,
            is_active=True,
            product__is_active=True,
            product__approval_status="APPROVED",
            stock_quantity__gt=0
        ).select_related(
            'product__seller',
            'product__subcategory',
        ).annotate(
            avg_rating=Coalesce(
                Avg(
                    "product__reviews__rating",
                    filter=Q(product__reviews__is_approved=True)
                ),
                Value(0.0)
            )
        ).prefetch_related(
            'images'
        )
        wishlist_ids = set()
        if request.user.is_authenticated:
            wishlist_ids = set(
                WishlistItem.objects.filter(
                    wishlist__user=request.user
                ).values_list("variant_id", flat=True)
            )
        variant_map = {}
        for v in trending_variants:
            if v.product.id not in variant_map:
                variant_map[v.product.id] = v
        ordered_variants = [
            variant_map[p_id]
            for p_id in product_ids
            if p_id in variant_map
        ]


        for variant in ordered_variants:


            primary_img = variant.images.filter(is_primary=True).first()
            variant.display_image = primary_img if primary_img else variant.images.first()

            variant.discount = variant.mrp - variant.selling_price

            variant.is_in_wishlist = variant.id in wishlist_ids

            variant.avg_rating = round(variant.avg_rating, 1)

            for item in trending_raw:
                if item['variant__product'] == variant.product.id:
                    variant.trending_rank = item['order_count']
                    break

            trending_products.append(variant)

    sort = request.GET.get('sort', 'trending')

    if sort == 'price_low':
        trending_products.sort(key=lambda v: float(v.selling_price))

    elif sort == 'price_high':
        trending_products.sort(key=lambda v: float(v.selling_price), reverse=True)

    paginator = Paginator(trending_products, 12)
    page = request.GET.get('page')
    trending_products_page_obj = paginator.get_page(page)

    return render(request, "core/trending.html", {
        'trending_products': trending_products_page_obj,
        'sort': sort,
        'total_trending': len(trending_products),
        'live_shoppers': 8200,
    })