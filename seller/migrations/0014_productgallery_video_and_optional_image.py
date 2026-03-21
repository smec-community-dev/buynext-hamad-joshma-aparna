from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("seller", "0013_productvariant_low_stock_threshold"),
    ]

    operations = [
        migrations.AddField(
            model_name="productgallery",
            name="video",
            field=models.FileField(blank=True, null=True, upload_to="product_videos/"),
        ),
        migrations.AlterField(
            model_name="productgallery",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="product_images/"),
        ),
    ]
