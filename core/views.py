from django.shortcuts import render,redirect,get_object_or_404
from .models import *
from seller.models import *
from customer.models import * 
from customer.models import WishlistItem
from django.db.models import Avg, Prefetch,Min,Max
from django.contrib.auth import authenticate,login,logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .decorator import _dashboard_for_user,customer_required,admin_not_required
# Create your views here.

def login_view(request):
    if request.method=="POST":
        username_or_email=request.POST.get("username_or_email")
        password=request.POST.get("password")
        try:
            user_obj=User.objects.get(email=username_or_email)
            username=user_obj.username
        except User.DoesNotExist:
            username=username_or_email
        user = authenticate(request,username=username,password=password)
        if user is not None:
            login(request,user)
            return redirect(_dashboard_for_user(request.user))
        else:
            messages.error(request, "Invalid username or password")
    return render(request,"core/login.html")
def register_view(request):
    if request.method=="POST":
        username=request.POST.get("username")
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
        if User.objects.filter( phone_number=phone_no).exists():
            messages.error(request, "phone number already registered")
            return render(request, "core/register.html")
        user=User.objects.create_user(
            username=username,
            email=email,
             phone_number=phone_no,
            password=password
        )
        user.is_active=True
        user.save()
        login(request, user)
        messages.success(request, "Registration successful! please login.")
        return redirect("login")
        
    return render(request,"core/register.html")
@admin_not_required
def home_view(request):
    show_all = request.GET.get('show_all', False)
    categories = Category.objects.filter(is_active=True).order_by('display_order', 'name')

    if not show_all:
        categories = categories[:8]

    return render(request,"core/home.html", {
        'categories': categories,
        'show_all': show_all,
        'total_categories': Category.objects.filter(is_active=True).count()
    })
@login_required
def logout_view(request):
    logout(request)
    return redirect("/")


from django.shortcuts import render
from django.db.models import Min
from django.core.paginator import Paginator

@admin_not_required
def all_products(request):

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

   
    if selected_ids:
        products = products.filter(subcategory__category__id__in=selected_ids)

    
    products = products.annotate(
        min_selling_price=Min("variants__selling_price"),
        min_mrp=Min("variants__mrp")
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

    paginator = Paginator(products, 2)
    page_number = request.GET.get("page")
    products = paginator.get_page(page_number)

    context = {
        "products": products,
        "categories": categories,
        "selected_categories": selected_ids,
        "sort_by": sort_by,
        "min_price": min_price,
        "max_price": max_price,
        "in_stock": in_stock,
    }

    return render(request, "core/all_products.html", context)


@admin_not_required
def subcategory_view(request, category_slug):

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
        stock_quantity=Max("variants__stock_quantity")
    )

   
    if sort == "price_low_high":
        products = products.order_by("min_selling_price")

    elif sort == "price_high_low":
        products = products.order_by("-min_selling_price")

    else:
        products = products.order_by("-created_at")

 
    for product in products:
        variant = product.variants.first()
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
    paginator = Paginator(products, 1) 
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

    default_variant = variants.filter(stock_quantity__gt=0).first()

    if not default_variant:
        default_variant = variants.first()

    if request.user.is_authenticated:
          default_variant.is_in_wishlist = default_variant.wishlist_items.filter(
        wishlist__user=request.user
    ).exists()
    else:
        default_variant.is_in_wishlist = False

    reviews = Review.objects.filter(
        product=product
    ).select_related("user").order_by("-created_at")

    rating_data = reviews.aggregate(avg=Avg("rating"))

    average_rating = round(rating_data["avg"] or 0, 1)

    review_count = reviews.count()

    context = {
        "product": product,
        "variants": variants,
        "gallery_images": gallery_images,
        "default_variant": default_variant,
        "reviews": reviews,
        "average_rating": average_rating,
        "review_count": review_count,
    }

    return render(request, "core/product_detail.html", context)
