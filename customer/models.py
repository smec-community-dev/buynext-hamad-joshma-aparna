import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import User, Address
from seller.models import Product, ProductVariant, SellerProfile


class Cart(models.Model):
  
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"Cart of {self.user.username}"

    @property
    def total_items(self):
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0

    @property
    def total_price(self):
        return sum(item.subtotal for item in self.items.all())


class CartItem(models.Model):
   
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name='cart_items'
    )
    quantity = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Must be at least 1"
    )
    price_at_time = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Snapshot of selling_price when item was added"
    )
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['cart', 'variant']]
        indexes = [
            models.Index(fields=['cart', 'variant']),
        ]

    def __str__(self):
        return f"{self.quantity}x {self.variant.sku_code} in {self.cart.user.username}'s cart"

    @property
    def subtotal(self):
        return self.price_at_time * self.quantity


class Wishlist(models.Model):
  
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlists')
    wishlist_name = models.CharField(max_length=100, default='My Wishlist')
    is_default = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False, help_text="Allow sharing via link")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['user', 'wishlist_name']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.wishlist_name}"


class WishlistItem(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name='wishlist_items'
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['wishlist', 'variant']]
        ordering = ['-added_at']
        indexes = [
            models.Index(fields=['wishlist', 'variant']),
        ]

    def __str__(self):
        return f"{self.variant.sku_code} in {self.wishlist.wishlist_name}"


class Review(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    title = models.CharField(max_length=150, blank=True, help_text="Short review headline")
    comment = models.TextField()
    is_verified_purchase = models.BooleanField(
        default=False,
        help_text="True if this user actually ordered this product"
    )
    is_approved = models.BooleanField(default=True, help_text="Admin moderation flag")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['user', 'product']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'is_approved']),
            models.Index(fields=['product', 'rating']),
            models.Index(fields=['user', 'product']),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.product.name} ({self.rating}★)"


class Order(models.Model):
  
    ORDER_STATUS = (
        ('PLACED', 'Placed'),
        ('CONFIRMED', 'Confirmed'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
        ('RETURN_REQUESTED', 'Return Requested'),
        ('RETURNED', 'Returned'),
        ('REFUNDED', 'Refunded'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(
        max_length=100, unique=True,
        help_text="Human-readable ID e.g. ORD-2024-00123"
    )

    # Address snapshot — stored as JSON to preserve address even if user edits it later
    shipping_address = models.JSONField(
        help_text="Snapshot of delivery address at time of order"
    )

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="total_amount - discount_amount"
    )

    coupon_code = models.CharField(max_length=50, blank=True)
    order_status = models.CharField(
        max_length=30, choices=ORDER_STATUS, default='PLACED', db_index=True
    )
    payment_method = models.CharField(max_length=50, blank=True)
    is_paid = models.BooleanField(default=False)
    note = models.TextField(blank=True, help_text="Customer note / special instructions")

    ordered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-ordered_at']
        indexes = [
            models.Index(fields=['user', 'order_status']),
            models.Index(fields=['order_number']),
            models.Index(fields=['order_status', '-ordered_at']),
            models.Index(fields=['is_paid']),
        ]

    def __str__(self):
        return f"{self.order_number} — {self.user.username} ({self.order_status})"

    def save(self, *args, **kwargs):
        # Auto-generate order number if not set
        if not self.order_number:
            from django.utils import timezone
            year = timezone.now().year
            last = Order.objects.filter(
                ordered_at__year=year
            ).order_by('-ordered_at').first()
            seq = 1
            if last and last.order_number:
                try:
                    seq = int(last.order_number.split('-')[-1]) + 1
                except (ValueError, IndexError):
                    seq = 1
            self.order_number = f"ORD-{year}-{seq:05d}"
        super().save(*args, **kwargs)


class OrderItem(models.Model):
 
    ITEM_STATUS = (
        ('ACTIVE', 'Active'),
        ('CANCELLED', 'Cancelled'),
        ('RETURN_REQUESTED', 'Return Requested'),
        ('RETURNED', 'Returned'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, related_name='order_items'
    )
    seller = models.ForeignKey(
        SellerProfile, on_delete=models.SET_NULL, null=True, related_name='order_items'
    )
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    price_at_purchase = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Locked selling_price at checkout; never changes after order placed"
    )
    item_status = models.CharField(
        max_length=20, choices=ITEM_STATUS, default='ACTIVE', db_index=True
    )

    class Meta:
        indexes = [
            models.Index(fields=['order', 'item_status']),
            models.Index(fields=['seller', 'item_status']),
            models.Index(fields=['variant']),
        ]

    def __str__(self):
        sku = self.variant.sku_code if self.variant else 'N/A'
        return f"{self.quantity}x {sku} in {self.order.order_number}"

    @property
    def subtotal(self):
        return self.price_at_purchase * self.quantity