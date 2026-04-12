from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from customer.models import OrderItem

def get_trending_products(days=7, limit=10):
    timeframe = timezone.now() - timedelta(days=days)

    return (
        OrderItem.objects.filter(created_at__gte=timeframe)
        .values('variant__product')   # ✅ product id
        .annotate(order_count=Count('id'))
        .order_by('-order_count')[:limit]
    )
