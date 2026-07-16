from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0023_order_orderitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='elibrarypdf',
            name='is_demo',
            field=models.BooleanField(
                default=False,
                verbose_name='Free Demo (visible without purchase)',
                help_text='Tick this to make the PDF freely accessible to all visitors as a demo.'
            ),
        ),
    ]
