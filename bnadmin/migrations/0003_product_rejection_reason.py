import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("bnadmin", "0002_initial"),
        ("core", "0008_alter_subcategory_id"),
        ("seller", "0014_productgallery_video_and_optional_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductRejectionReason",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ("reason", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="product_rejections",
                    to="core.user",
                )),
                ("product", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rejection_reasons",
                    to="seller.product",
                )),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="productrejectionreason",
            index=models.Index(fields=["product", "-created_at"], name="bnadmin_pr_product_9f6b7f_idx"),
        ),
    ]
