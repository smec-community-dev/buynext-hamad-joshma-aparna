import uuid
import string
import random
from django.db import models
from django.utils.text import slugify
from core.models import User, SubCategory


def generate_unique_sku(instance):

    brand_prefix = ''.join(filter(str.isalpha, instance.product.brand))[:3].upper()
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{brand_prefix}-{random_str}"


class SellerProfile(models.Model):
 
    VERIFICATION_STATUS = (
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller_profile')
    store_name = models.CharField(max_length=255)
    store_slug = models.SlugField(max_length=270, unique=True, blank=True)
    gst_number = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, help_text="Store bio/description shown to customers")
    logo = models.ImageField(upload_to='seller_logos/', null=True, blank=True)
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='PENDING',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['store_slug']),
            models.Index(fields=[ 'verification_status']),
        ]

    def __str__(self):
        return f"{self.store_name} ({self.user.username})"

    def save(self, *args, **kwargs):
        if not self.store_slug:
            base_slug = slugify(self.store_name)
            slug = base_slug
            counter = 1
            while SellerProfile.objects.filter(store_slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.store_slug = slug
        super().save(*args, **kwargs)


class Product(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        SellerProfile, on_delete=models.CASCADE, related_name='products'
    )
    subcategory = models.ForeignKey(
        SubCategory, on_delete=models.SET_NULL, null=True, related_name='products'
    )
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['seller', 'is_active']),
            models.Index(fields=['brand', 'is_active']),
            models.Index(fields=['subcategory', 'is_active']),
        ]

    def __str__(self):
        return f"{self.brand} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.brand}-{self.name}")
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class ProductVariant(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku_code = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        help_text="Auto-generated: BRD-XXXXXX format"
    )
    slug = models.SlugField(max_length=320, unique=True, blank=True)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, help_text="Maximum Retail Price")
    selling_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Actual selling price; must be <= MRP"
    )
    stock_quantity = models.IntegerField(default=0, help_text="Current available stock")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sku_code']),
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['selling_price']),
            models.Index(fields=['stock_quantity']),
        ]

    def __str__(self):
        return f"{self.product.name} | SKU: {self.sku_code}"

    def save(self, *args, **kwargs):
        # Auto-generate slug using product name + first 4 hex chars of UUID
        if not self.slug:
            self.slug = slugify(f"{self.product.name}-{str(self.id.hex[:4])}")

        # Auto-generate unique SKU
        if not self.sku_code:
            sku = generate_unique_sku(self)
            while ProductVariant.objects.filter(sku_code=sku).exists():
                sku = generate_unique_sku(self)
            self.sku_code = sku

        super().save(*args, **kwargs)

    @property
    def discount_percentage(self):
        if self.mrp > 0:
            return round(((self.mrp - self.selling_price) / self.mrp) * 100, 2)
        return 0

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0


class ProductImage(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name='images'
    )
    image_url = models.URLField(help_text="CDN-hosted image URL")
    alt_text = models.CharField(max_length=255, blank=True, help_text="Alt text for accessibility")
    is_primary = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'display_order']
        indexes = [
            models.Index(fields=['variant', 'is_primary']),
        ]

    def __str__(self):
        return f"{'[Primary] ' if self.is_primary else ''}Image for {self.variant.sku_code}"

    def save(self, *args, **kwargs):
        # Ensure only one primary image per variant
        if self.is_primary:
            ProductImage.objects.filter(variant=self.variant, is_primary=True).exclude(
                pk=self.pk
            ).update(is_primary=False)
        super().save(*args, **kwargs)


class Attribute(models.Model):

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class AttributeOption(models.Model):
 
    attribute = models.ForeignKey(
        Attribute, on_delete=models.CASCADE, related_name='options'
    )
    value = models.CharField(max_length=100)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['attribute', 'display_order', 'value']
        unique_together = [['attribute', 'value']]
        indexes = [
            models.Index(fields=['attribute', 'value']),
        ]

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.attribute.name}-{self.value}")
        super().save(*args, **kwargs)


class VariantAttributeBridge(models.Model):
 
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name='variant_attributes'
    )
    option = models.ForeignKey(
        AttributeOption, on_delete=models.CASCADE, related_name='variant_attributes'
    )

    class Meta:
        unique_together = [['variant', 'option']]
        indexes = [
            models.Index(fields=['variant', 'option']),
        ]

    def __str__(self):
        return f"{self.variant.sku_code} → {self.option}"


class InventoryLog(models.Model):
  
    REASON_CHOICES = (
        ('PURCHASE', 'Customer Purchase'),
        ('RETURN', 'Customer Return'),
        ('RESTOCK', 'Manual Restock'),
        ('ADJUSTMENT', 'Manual Adjustment'),
        ('DAMAGE', 'Damaged / Lost'),
        ('CANCELLED', 'Order Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name='inventory_logs'
    )
    change_amount = models.IntegerField(
        help_text="Positive = restock / return. Negative = purchase / damage."
    )
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    reference_id = models.CharField(
        max_length=100, blank=True,
        help_text="Optional: order number or adjustment ID"
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['variant', 'reason']),
            models.Index(fields=['variant', '-created_at']),
        ]

    def __str__(self):
        sign = '+' if self.change_amount > 0 else ''
        return f"{self.variant.sku_code} | {sign}{self.change_amount} ({self.reason})"