from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from core.decorator import admin_required
from core.models import Category, SubCategory, User
from customer.models import Order, OrderItem
from .models import ProductRejectionReason
from seller.models import (
    Attribute,
    AttributeOption,
    Product,
    ProductVariant,
    SellerProfile,
)


def _seller_review_queue():
    return SellerProfile.objects.filter(
        Q(verification_status="PENDING")
        | Q(
            verification_status="REJECTED",
            verified_at__isnull=False,
            updated_at__gt=F("verified_at"),
        )
    ).select_related("user")


def _product_variant_label(variant):
    bridges = list(variant.variant_attributes.all())
    if not bridges:
        return variant.sku_code or "Standard", []

    values = [bridge.option.value for bridge in bridges]
    details = [
        {"name": bridge.option.attribute.name, "value": bridge.option.value}
        for bridge in bridges
    ]
    return " / ".join(values), details


@admin_required
def admin_dashboard(request):
    recent_sellers = (
        SellerProfile.objects.select_related("user").order_by("-created_at")[:5]
    )
    recent_products_qs = (
        Product.objects.select_related("seller", "seller__user")
        .prefetch_related("gallery", "variants__images")
        .order_by("-created_at")[:5]
    )
    recent_products = []
    for product in recent_products_qs:
        image_url = ""
        for media in product.gallery.all():
            if media.image:
                image_url = media.image.url
                break
        if not image_url:
            for variant in product.variants.all():
                for image in variant.images.all():
                    if image.image:
                        image_url = image.image.url
                        break
                if image_url:
                    break
        product.preview_image_url = image_url
        recent_products.append(product)
    recent_customers = User.objects.filter(role="CUSTOMER").order_by("-date_joined")[:5]
    annual_revenue = (
        Order.objects.filter(is_paid=True).aggregate(total=Sum("final_amount"))["total"]
        or 0
    )
    total_orders = Order.objects.count()
    total_products = Product.objects.count()
    total_sellers = SellerProfile.objects.count()

    def _pct(value, total):
        return round((value / total) * 100, 1) if total else 0

    product_approved = Product.objects.filter(approval_status="APPROVED").count()
    product_pending = Product.objects.filter(approval_status="PENDING").count()
    product_rejected = Product.objects.filter(approval_status="REJECTED").count()
    product_visible_total = product_approved + product_pending + product_rejected

    seller_verified = SellerProfile.objects.filter(verification_status="VERIFIED").count()
    seller_pending = SellerProfile.objects.filter(verification_status="PENDING").count()
    seller_rejected = SellerProfile.objects.filter(verification_status="REJECTED").count()

    order_in_progress = Order.objects.filter(
        order_status__in=[
            "PLACED",
            "CONFIRMED",
            "PROCESSING",
            "SHIPPED",
            "OUT_FOR_DELIVERY",
        ]
    ).count()
    order_delivered = Order.objects.filter(order_status="DELIVERED").count()
    order_exception = Order.objects.filter(
        order_status__in=["CANCELLED", "RETURN_REQUESTED", "RETURNED", "REFUNDED"]
    ).count()

    context = {
        "total_sellers": total_sellers,
        "total_orders": total_orders,
        "annual_revenue": annual_revenue,
        "total_products": total_products,
        "recent_sellers": recent_sellers,
        "recent_products": recent_products,
        "recent_customers": recent_customers,
        "product_approved": product_approved,
        "product_pending": product_pending,
        "product_rejected": product_rejected,
        "product_visible_total": product_visible_total,
        "product_approved_pct": _pct(product_approved, product_visible_total),
        "product_pending_pct": _pct(product_pending, product_visible_total),
        "product_rejected_pct": _pct(product_rejected, product_visible_total),
        "seller_verified": seller_verified,
        "seller_pending": seller_pending,
        "seller_rejected": seller_rejected,
        "seller_verified_pct": _pct(seller_verified, total_sellers),
        "seller_pending_pct": _pct(seller_pending, total_sellers),
        "seller_rejected_pct": _pct(seller_rejected, total_sellers),
        "order_in_progress": order_in_progress,
        "order_delivered": order_delivered,
        "order_exception": order_exception,
        "order_in_progress_pct": _pct(order_in_progress, total_orders),
        "order_delivered_pct": _pct(order_delivered, total_orders),
        "order_exception_pct": _pct(order_exception, total_orders),
    }
    return render(request, "bnadmin/dashboard.html", context)


@admin_required
def user_management(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    users = User.objects.filter(role="CUSTOMER")
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone_number__icontains=query)
        )
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)

    users = users.order_by("-date_joined")
    return render(
        request,
        "bnadmin/usermanagement.html",
        {"users": users, "q": query, "selected_status": status},
    )


@admin_required
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        user.username = request.POST.get("username", user.username).strip()
        user.first_name = request.POST.get("first_name", user.first_name).strip()
        user.last_name = request.POST.get("last_name", user.last_name).strip()
        user.email = request.POST.get("email", user.email).strip()

        phone_number = request.POST.get("phone_number", "").strip()
        user.phone_number = phone_number or None

        user.is_active = request.POST.get("status") == "true"
        try:
            user.save()
            messages.success(request, "Customer details updated successfully.")
            return redirect("usermanagement")
        except IntegrityError:
            messages.error(
                request,
                "Unable to save customer. Username or phone number may already exist.",
            )

    return render(request, "bnadmin/edit_customer.html", {"user_obj": user})


@admin_required
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id, role="CUSTOMER")
    user.delete()
    return redirect("usermanagement")


@admin_required
def customer_orders(request, user_id):
    customer = get_object_or_404(User, id=user_id, role="CUSTOMER")
    orders = (
        Order.objects.filter(user=customer)
        .prefetch_related("items__variant__product", "items__seller")
        .order_by("-ordered_at")
    )

    order_stats = {
        "total": orders.count(),
        "delivered": orders.filter(order_status="DELIVERED").count(),
        "cancelled": orders.filter(order_status="CANCELLED").count(),
        "revenue": orders.aggregate(total=Sum("final_amount"))["total"] or 0,
    }

    return render(
        request,
        "bnadmin/customer_orders.html",
        {
            "customer": customer,
            "orders": orders,
            "order_stats": order_stats,
        },
    )


@admin_required
def seller_management(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip().upper()

    pending_sellers = _seller_review_queue()
    verified_sellers = SellerProfile.objects.filter(
        verification_status="VERIFIED"
    ).select_related("user")

    if query:
        seller_filter = (
            Q(store_name__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(user__phone_number__icontains=query)
        )
        pending_sellers = pending_sellers.filter(seller_filter)
        verified_sellers = verified_sellers.filter(seller_filter)

    if status == "VERIFIED":
        pending_sellers = SellerProfile.objects.none()
    elif status == "PENDING":
        pending_sellers = pending_sellers.filter(verification_status="PENDING")
        verified_sellers = SellerProfile.objects.none()
    elif status == "REJECTED":
        pending_sellers = pending_sellers.filter(verification_status="REJECTED")
        verified_sellers = SellerProfile.objects.none()

    seller_stats = {
        "total": SellerProfile.objects.count(),
        "pending": _seller_review_queue().count(),
        "verified": SellerProfile.objects.filter(verification_status="VERIFIED").count(),
        "rejected": SellerProfile.objects.filter(verification_status="REJECTED").count(),
    }

    return render(
        request,
        "bnadmin/sellermanagement.html",
        {
            "pending_sellers": pending_sellers,
            "verified_sellers": verified_sellers,
            "seller_stats": seller_stats,
            "q": query,
            "selected_status": status,
            "default_tab": "verification"
            if status in {"PENDING", "REJECTED"}
            else "seller",
        },
    )


@admin_required
def verify_seller(request, seller_id):
    seller = get_object_or_404(SellerProfile, id=seller_id)
    seller.verification_status = "VERIFIED"
    seller.rejection_reason = ""
    seller.save()
    SellerProfile.objects.filter(pk=seller.pk).update(verified_at=seller.updated_at)
    seller.user.is_verified = True
    seller.user.save(update_fields=["is_verified"])
    messages.success(request, "Seller verified successfully")
    return redirect("seller_management")


@admin_required
def reject_seller(request, seller_id):
    seller = get_object_or_404(SellerProfile, id=seller_id)
    seller.verification_status = "REJECTED"
    seller.save()
    SellerProfile.objects.filter(pk=seller.pk).update(verified_at=seller.updated_at)
    seller.user.is_verified = False
    seller.user.save(update_fields=["is_verified"])
    messages.warning(request, "Seller rejected")
    return redirect("seller_management")


@admin_required
def edit_seller(request, seller_id):
    seller = get_object_or_404(SellerProfile, id=seller_id)

    if request.method == "POST":
        seller.user.username = request.POST.get("username", seller.user.username).strip()
        seller.user.first_name = request.POST.get(
            "first_name", seller.user.first_name
        ).strip()
        seller.user.last_name = request.POST.get(
            "last_name", seller.user.last_name
        ).strip()
        seller.user.email = request.POST.get("email", seller.user.email).strip()
        phone_number = request.POST.get("phone_number", "").strip()
        seller.user.phone_number = phone_number or None
        seller.user.is_active = request.POST.get("status") == "true"

        seller.store_name = request.POST.get("store_name", seller.store_name).strip()

        try:
            seller.user.save()
            seller.save()
            messages.success(request, "Seller profile updated successfully.")
            return redirect("seller_management")
        except IntegrityError:
            messages.error(
                request,
                "Unable to save seller profile. Username, email, or phone number may already exist.",
            )

    return render(request, "bnadmin/edit_seller.html", {"seller": seller})


@admin_required
def seller_product_report(request, seller_id):
    seller = get_object_or_404(
        SellerProfile.objects.select_related("user"), id=seller_id
    )
    products = (
        Product.objects.filter(seller=seller)
        .annotate(
            orders_count=Count("variants__order_items__order", distinct=True),
            units_sold=Coalesce(Sum("variants__order_items__quantity"), 0),
        )
        .order_by("-orders_count", "-units_sold", "name")
    )

    order_items = OrderItem.objects.filter(seller=seller)
    report_stats = {
        "products": products.count(),
        "orders": order_items.values("order_id").distinct().count(),
        "units": order_items.aggregate(total=Sum("quantity"))["total"] or 0,
    }

    return render(
        request,
        "bnadmin/seller_product_report.html",
        {
            "seller": seller,
            "products": products,
            "report_stats": report_stats,
        },
    )


@admin_required
def delete_seller(request, seller_id):
    seller = get_object_or_404(SellerProfile, id=seller_id)
    seller.user.delete()
    messages.success(request, "Seller deleted successfully")
    return redirect("seller_management")


@admin_required
def order_management(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    orders = (
        Order.objects.select_related("user")
        .prefetch_related("items")
        .order_by("-ordered_at")
    )
    if query:
        order_filter = (
            Q(order_number__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
        )
        try:
            import uuid
            order_filter = order_filter | Q(id=uuid.UUID(query))
        except (ValueError, TypeError):
            pass
        orders = orders.filter(order_filter)
    if status:
        orders = orders.filter(order_status=status)

    order_stats = {
        "total": Order.objects.count(),
        "delivered": Order.objects.filter(order_status="DELIVERED").count(),
        "cancelled": Order.objects.filter(order_status="CANCELLED").count(),
        "revenue": Order.objects.filter(is_paid=True).aggregate(total=Sum("final_amount"))["total"] or 0,
    }

    return render(
        request,
        "bnadmin/orders.html",
        {
            "orders": orders,
            "order_stats": order_stats,
            "q": query,
            "selected_status": status,
            "status_choices": Order.ORDER_STATUS,
        },
    )


@admin_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related(
            "items__variant__product",
            "items__seller",
        ),
        id=order_id,
    )
    order_items = order.items.all()
    total_units = order_items.aggregate(total=Sum("quantity"))["total"] or 0
    seller_count = order_items.values("seller_id").distinct().count()
    return render(
        request,
        "bnadmin/order_detail.html",
        {
            "order": order,
            "order_items": order_items,
            "total_units": total_units,
            "seller_count": seller_count,
        },
    )


@admin_required
def product_verification(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip().upper()
    subcategory_id = request.GET.get("subcategory", "").strip()

    all_products = (
        Product.objects.select_related("seller", "seller__user", "subcategory")
        .prefetch_related("gallery", "variants")
        .order_by("-created_at")
    )
    if query:
        all_products = all_products.filter(
            Q(name__icontains=query)
            | Q(brand__icontains=query)
            | Q(seller__store_name__icontains=query)
            | Q(seller__user__username__icontains=query)
        )
    if subcategory_id:
        all_products = all_products.filter(subcategory_id=subcategory_id)
    if status in {"APPROVED", "PENDING"}:
        all_products = all_products.filter(approval_status=status)

    pending_products = all_products.filter(approval_status="PENDING")
    approved_products_qs = all_products.filter(approval_status="APPROVED")
    approved_products = list(approved_products_qs)
    for product in approved_products:
        variants = list(product.variants.all())
        active_variants = [v for v in variants if v.is_active]
        candidate_variants = active_variants or variants
        product.total_stock = sum(v.stock_quantity for v in variants) if variants else 0
        if candidate_variants:
            selected = min(candidate_variants, key=lambda v: v.selling_price or 0)
            product.display_price = selected.selling_price
            product.display_mrp = selected.mrp
            product.display_discount = (
                selected.discount_percentage if selected.discount_percentage else 0
            )
        else:
            product.display_price = None
            product.display_mrp = None
            product.display_discount = 0
    product_stats = {
        "total": approved_products_qs.count(),
        "pending": pending_products.count(),
        "approved": approved_products_qs.count(),
        "rejected": all_products.filter(approval_status="REJECTED").count(),
    }
    subcategories = SubCategory.objects.select_related("category").order_by(
        "category__display_order",
        "display_order",
        "name",
    )

    return render(
        request,
        "bnadmin/bbb_productverification.html",
        {
            "pending_products": pending_products,
            "all_products": approved_products,
            "product_stats": product_stats,
            "subcategories": subcategories,
            "q": query,
            "selected_status": status,
            "selected_subcategory": subcategory_id,
            "default_tab": "verification"
            if status == "PENDING"
            else "all",
        },
    )


@admin_required
def admin_product_preview(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related(
            "seller",
            "seller__user",
            "subcategory",
            "subcategory__category",
        ).prefetch_related(
            "gallery",
            Prefetch(
                "variants",
                queryset=ProductVariant.objects.prefetch_related(
                    "images",
                    "variant_attributes__option__attribute",
                ).order_by("-is_active", "selling_price", "created_at"),
            ),
        ),
        id=product_id,
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

    fallback_image_url = gallery_images[0]["url"] if gallery_images else ""

    variant_cards = []
    variant_payload = []

    for variant in variants:
        label, attributes = _product_variant_label(variant)
        variant_image = next(
            (image.image.url for image in variant.images.all() if image.image),
            fallback_image_url,
        )

        variant_cards.append(
            {
                "id": str(variant.id),
                "label": label,
                "attributes": attributes,
                "sku": variant.sku_code,
                "price": variant.selling_price,
                "mrp": variant.mrp,
                "stock_quantity": variant.stock_quantity,
                "discount": variant.discount_percentage,
                "is_active": variant.is_active,
                "is_in_stock": variant.is_in_stock,
                "image_url": variant_image,
            }
        )

        variant_payload.append(
            {
                "id": str(variant.id),
                "label": label,
                "sku": variant.sku_code,
                "price": f"{variant.selling_price:.2f}",
                "mrp": f"{variant.mrp:.2f}",
                "stock": variant.stock_quantity,
                "discount": variant.discount_percentage,
                "is_active": variant.is_active,
                "is_in_stock": variant.is_in_stock,
                "image_url": variant_image,
                "attribute_summary": ", ".join(
                    f"{detail['name']}: {detail['value']}" for detail in attributes
                ),
            }
        )

    next_url = request.GET.get("next", "")
    back_url = (
        next_url
        if next_url
        and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
        else ""
    )

    context = {
        "product": product,
        "gallery_images": gallery_images,
        "variant_cards": variant_cards,
        "variant_payload": variant_payload,
        "primary_variant": primary_variant,
        "primary_variant_id": str(primary_variant.id) if primary_variant else "",
        "latest_rejection": product.rejection_reasons.first(),
        "back_url": back_url,
        "back_label": "Back to report" if back_url else "Back to products",
    }

    return render(request, "bnadmin/product_preview.html", context)


@admin_required
def edit_product_admin(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method != "POST":
        return redirect("product_verification")

    name = request.POST.get("name", "").strip()
    brand = request.POST.get("brand", "").strip()
    subcategory_id = request.POST.get("subcategory", "").strip()

    if not name or not brand:
        messages.error(request, "Product name and brand are required.")
        return redirect("product_verification")

    product.name = name
    product.brand = brand
    product.subcategory = (
        get_object_or_404(SubCategory, id=subcategory_id) if subcategory_id else None
    )
    product.save()
    messages.success(request, "Product updated successfully.")
    return redirect("product_verification")


@admin_required
def delete_product_admin(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.delete()
    return redirect("product_verification")


@admin_required
def approve_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.approval_status = "APPROVED"
    product.save()
    messages.success(request, "Product approved successfully")
    return redirect("product_verification")


@admin_required
def reject_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method != "POST":
        messages.error(request, "Rejection reason is required.")
        return redirect("product_verification")

    reason = request.POST.get("rejection_reason", "").strip()
    if not reason:
        messages.error(request, "Rejection reason is required.")
        return redirect("product_verification")

    product.approval_status = "REJECTED"
    product.save()
    ProductRejectionReason.objects.create(
        product=product,
        reason=reason,
        created_by=request.user if request.user.is_authenticated else None,
    )
    messages.warning(request, "Product rejected")
    return redirect("product_verification")


@admin_required
def admin_search(request):
    query = request.GET.get("q", "").strip()

    customers = User.objects.none()
    sellers = SellerProfile.objects.none()
    orders = Order.objects.none()
    products = Product.objects.none()

    if query:
        customers = (
            User.objects.filter(role="CUSTOMER")
            .filter(
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
                | Q(phone_number__icontains=query)
            )
            .order_by("-date_joined")[:10]
        )

        sellers = (
            SellerProfile.objects.select_related("user")
            .filter(
                Q(store_name__icontains=query)
                | Q(user__username__icontains=query)
                | Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__email__icontains=query)
                | Q(user__phone_number__icontains=query)
            )
            .order_by("-updated_at")[:10]
        )

        orders = (
            Order.objects.select_related("user")
            .filter(
                Q(order_number__icontains=query)
                | Q(user__username__icontains=query)
                | Q(user__email__icontains=query)
            )
            .order_by("-ordered_at")[:10]
        )

        products = (
            Product.objects.select_related("seller")
            .filter(
                Q(name__icontains=query)
                | Q(brand__icontains=query)
                | Q(seller__store_name__icontains=query)
            )
            .order_by("-created_at")[:10]
        )

    context = {
        "q": query,
        "customers": customers,
        "sellers": sellers,
        "orders": orders,
        "products": products,
        "total_results": len(customers) + len(sellers) + len(orders) + len(products),
    }
    return render(request, "bnadmin/search_results.html", context)


@admin_required
def catalogue_management(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    categories = Category.objects.prefetch_related(
        "subcategories__attributes__options"
    ).all()

    if status == "active":
        categories = categories.filter(is_active=True)
    elif status == "inactive":
        categories = categories.filter(is_active=False)

    if query:
        categories = categories.filter(
            Q(name__icontains=query)
            | Q(subcategories__name__icontains=query)
            | Q(subcategories__attributes__name__icontains=query)
            | Q(subcategories__attributes__options__value__icontains=query)
        ).distinct()

    return render(
        request,
        "bnadmin/cataloguemanagement.html",
        {"categories": categories, "q": query, "selected_status": status},
    )


@admin_required
def add_category(request):
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        display_order = request.POST.get("order") or 0
        is_active = request.POST.get("is_active") == "on"
        image = request.FILES.get("image")
        if Category.objects.filter(name=name).exists():
            messages.error(request, "Category with this name already exists.")
            return redirect("add_category")
        if Category.objects.filter(display_order=display_order).exists():
            messages.error(request, f"Display order {display_order} is already taken.")
            return redirect("add_category")

        Category.objects.create(
            name=name,
            description=description,
            display_order=display_order,
            is_active=is_active,
            image=image,
        )
        messages.success(request, "Category created successfully.")
        return redirect("catalogue_management")
    return render(request, "bnadmin/addcategory.html")


@admin_required
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        category.name = request.POST.get("name")
        category.description = request.POST.get("description")
        category.display_order = request.POST.get("order") or 0
        category.is_active = request.POST.get("is_active") == "on"

        if request.FILES.get("image"):
            if category.image:
                category.image.delete(save=False)
            category.image = request.FILES.get("image")

        category.save()

        messages.success(request, "Category updated successfully.")
        return redirect("catalogue_management")

    return render(request, "bnadmin/edit_category.html", {"category": category})


@admin_required
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if category.image:
        category.image.delete(save=False)
    category.delete()
    messages.success(request, "Category deleted successfully.")

    return redirect("catalogue_management")


@admin_required
def add_subcategory(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == "POST":
        selected_category_id = request.POST.get("category")
        name = request.POST.get("name")
        description = request.POST.get("description")
        display_order = request.POST.get("order") or 0
        is_active = request.POST.get("is_active") == "on"
        image = request.FILES.get("image")
        if not selected_category_id:
            messages.error(request, "Please select a category.")
            return redirect("add_subcategory", category_id=category.id)
        category = Category.objects.get(id=selected_category_id)
        if SubCategory.objects.filter(category=category, name=name).exists():
            messages.error(request, "SubCategory already exists in this category.")
            return redirect("add_subcategory", category_id=category.id)
        if SubCategory.objects.filter(
            category=category, display_order=display_order
        ).exists():
            messages.error(request, f"Display order {display_order} is already taken.")
            return redirect("add_subcategory", category_id=category.id)
        SubCategory.objects.create(
            category=category,
            name=name,
            description=description,
            image=image,
            display_order=display_order,
            is_active=is_active,
        )
        messages.success(request, "SubCategory created successfully.")
        return redirect("catalogue_management")
    return render(request, "bnadmin/addsubcategory.html", {"category": category})


@admin_required
def edit_subcategory(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    category = subcategory.category
    if request.method == "POST":
        subcategory.name = request.POST.get("name")
        subcategory.description = request.POST.get("description")
        subcategory.display_order = request.POST.get("order") or 0
        subcategory.is_active = request.POST.get("is_active") == "on"
        if request.FILES.get("image"):
            if subcategory.image:
                subcategory.image.delete(save=False)
            subcategory.image = request.FILES.get("image")
        subcategory.save()
        messages.success(request, "SubCategory updated successfully.")
        return redirect("catalogue_management")

    return render(
        request,
        "bnadmin/edit_subcategory.html",
        {"subcategory": subcategory, "category": category},
    )


@admin_required
def delete_subcategory(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    if subcategory.image:
        subcategory.image.delete(save=False)
    subcategory.delete()
    messages.success(request, "SubCategory deleted successfully.")
    return redirect("catalogue_management")


@admin_required
def add_attribute(request):
    subcategories = SubCategory.objects.filter(is_active=True).order_by("display_order")
    if request.method == "POST":
        name = request.POST.get("name")
        display_order = request.POST.get("order") or 0
        subcategory_ids = request.POST.getlist("subcategories")
        if Attribute.objects.filter(name__iexact=name).exists():
            messages.error(request, "Attribute with this name already exists.")
            return redirect("add_attribute")
        attribute = Attribute.objects.create(name=name, display_order=display_order)
        if subcategory_ids:
            attribute.subcategories.set(subcategory_ids)
        messages.success(request, "Attribute created successfully.")
        return redirect("catalogue_management")
    return render(request, "bnadmin/addattribute.html", {"subcategories": subcategories})


@admin_required
def edit_attribute(request, attribute_id):
    attribute = get_object_or_404(Attribute, id=attribute_id)
    subcategories = SubCategory.objects.all().order_by("name")

    if request.method == "POST":
        name = request.POST.get("name")
        subcategory_ids = request.POST.getlist("subcategories")

        if Attribute.objects.filter(name__iexact=name).exclude(id=attribute.id).exists():
            messages.error(request, "Attribute with this name already exists.")
            return redirect("edit_attribute", attribute_id=attribute.id)

        attribute.name = name
        attribute.save()
        attribute.subcategories.set(subcategory_ids)
        messages.success(request, "Attribute updated successfully.")
        return redirect("catalogue_management")
    return render(
        request,
        "bnadmin/edit_attribute.html",
        {"attribute": attribute, "subcategories": subcategories},
    )


@admin_required
def delete_attribute(request, attribute_id):
    attribute = get_object_or_404(Attribute, id=attribute_id)
    attribute.delete()
    messages.success(request, "Attribute deleted successfully.")
    return redirect("catalogue_management")


@admin_required
def add_attributeoptions(request):
    attributes = Attribute.objects.all().order_by("name")
    selected_attribute_id = request.GET.get("attribute", "")

    if request.method == "POST":
        attribute_id = request.POST.get("attribute")
        value = request.POST.get("value")
        display_order = request.POST.get("order") or 0

        if not attribute_id:
            messages.error(request, "Please select an attribute.")
            return redirect("add_attributeoptions")

        attribute = get_object_or_404(Attribute, id=attribute_id)
        if AttributeOption.objects.filter(attribute=attribute, value=value).exists():
            messages.error(
                request, "This option already exists for the selected attribute."
            )
            return redirect("add_attributeoptions")
        AttributeOption.objects.create(
            attribute=attribute,
            value=value,
            display_order=display_order,
        )
        messages.success(request, "Attribute option added successfully.")
        return redirect("catalogue_management")
    return render(
        request,
        "bnadmin/addattributeoptions.html",
        {
            "attributes": attributes,
            "selected_attribute_id": selected_attribute_id,
        },
    )


@admin_required
def delete_attribute_option(request, option_id):
    option = get_object_or_404(AttributeOption, id=option_id)
    option.delete()
    messages.success(request, "Attribute option deleted successfully.")
    return redirect("catalogue_management")
