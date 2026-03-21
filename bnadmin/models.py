import uuid
from django.db import models
from django.utils.text import slugify
from core.models import Category, User
from seller.models import Product, SellerProfile
from customer.models import OrderItem


class Offer(models.Model):

    OFFER_TYPE = (
        ('PRODUCT', 'Product Offer'),
        ('CATEGORY', 'Category Offer'),
        ('SITE_WIDE', 'Site-Wide Offer'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=270, unique=True, blank=True)
    description = models.TextField(blank=True)
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPE, default='PRODUCT', db_index=True)
    banner_image = models.ImageField(upload_to='offer_banners/', null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'offer_type']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.title} ({'Active' if self.is_active else 'Inactive'})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Offer.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Discount(models.Model):

    DISCOUNT_TYPE = (
        ('PERCENTAGE', 'Percentage (%)'),
        ('FLAT', 'Flat Amount (₹)'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="e.g. '10% Off', 'Flat ₹200 Off'")
    discount_type = models.CharField(
        max_length=20, choices=DISCOUNT_TYPE, default='PERCENTAGE', db_index=True
    )
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Percentage (0-100) or flat amount in ₹"
    )
    min_order_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Minimum cart value to apply this discount"
    )
    max_discount_cap = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Maximum discount amount (for percentage discounts)"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'discount_type']),
        ]

    def __str__(self):
        symbol = '%' if self.discount_type == 'PERCENTAGE' else '₹'
        return f"{self.name} ({symbol}{self.discount_value})"


class Coupon(models.Model):

    COUPON_TYPE = (
        ('SINGLE_USE', 'Single Use Per User'),
        ('MULTI_USE', 'Multi Use'),
        ('ONE_TIME', 'One Time Total'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    discount = models.ForeignKey(
        Discount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coupons',
        help_text="Discount rule this coupon activates"
    )
    coupon_type = models.CharField(max_length=20, choices=COUPON_TYPE, default='MULTI_USE')
    usage_limit = models.IntegerField(
        default=1, help_text="Max total redemptions (0 = unlimited)"
    )
    used_count = models.IntegerField(default=0)
    min_order_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Minimum order value to apply coupon"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"COUPON: {self.code} ({self.used_count}/{self.usage_limit} used)"

    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if self.usage_limit > 0 and self.used_count >= self.usage_limit:
            return False
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True


# ── Bridge / Association Tables ────────────────────────────────────────────────

class OfferDiscountBridge(models.Model):
    """M2M: Attach one or more Discounts to an Offer bundle."""

    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='offer_discounts')
    discount = models.ForeignKey(Discount, on_delete=models.CASCADE, related_name='offer_discounts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['offer', 'discount']]
        indexes = [
            models.Index(fields=['offer', 'discount']),
        ]

    def __str__(self):
        return f"{self.offer.title} ← {self.discount.name}"


class ProductOfferBridge(models.Model):

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_offers')
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='product_offers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['product', 'offer']]
        indexes = [
            models.Index(fields=['product', 'offer']),
        ]

    def __str__(self):
        return f"{self.product.name} ← {self.offer.title}"


class CategoryOfferBridge(models.Model):

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='category_offers')
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='category_offers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['category', 'offer']]
        indexes = [
            models.Index(fields=['category', 'offer']),
        ]

    def __str__(self):
        return f"{self.category.name} ← {self.offer.title}"


class ProductDiscountBridge(models.Model):

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_discounts')
    discount = models.ForeignKey(Discount, on_delete=models.CASCADE, related_name='product_discounts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['product', 'discount']]
        indexes = [
            models.Index(fields=['product', 'discount']),
        ]

    def __str__(self):
        return f"{self.product.name} ← {self.discount.name}"


class CategoryDiscountBridge(models.Model):
  
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='category_discounts')
    discount = models.ForeignKey(Discount, on_delete=models.CASCADE, related_name='category_discounts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['category', 'discount']]
        indexes = [
            models.Index(fields=['category', 'discount']),
        ]

    def __str__(self):
        return f"{self.category.name} ← {self.discount.name}"


class PlatformCommission(models.Model):

    SETTLEMENT_STATUS = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SETTLED', 'Settled'),
        ('DISPUTED', 'Disputed'),
        ('ON_HOLD', 'On Hold'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        SellerProfile, on_delete=models.CASCADE, related_name='commissions'
    )
    order_item = models.OneToOneField(
        OrderItem, on_delete=models.CASCADE, related_name='commission'
    )
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Commission rate (%) applied at time of sale"
    )
    commission_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Actual ₹ commission charged on this order item"
    )
    settlement_status = models.CharField(
        max_length=20, choices=SETTLEMENT_STATUS, default='PENDING', db_index=True
    )
    settled_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller', 'settlement_status']),
            models.Index(fields=['settlement_status', '-created_at']),
        ]

    def __str__(self):
        return f"Commission ₹{self.commission_amount} | {self.seller.store_name} | {self.settlement_status}"


class ProductRejectionReason(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="rejection_reasons"
    )
    reason = models.TextField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_rejections",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "-created_at"]),
        ]

    def __str__(self):
        return f"Rejection for {self.product.name}"
