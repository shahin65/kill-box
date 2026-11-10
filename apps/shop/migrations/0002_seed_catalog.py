from django.db import migrations


def seed_forward(apps, schema_editor):
    GemPackage = apps.get_model('shop', 'GemPackage')
    DigitalProduct = apps.get_model('shop', 'DigitalProduct')
    PhysicalProduct = apps.get_model('shop', 'PhysicalProduct')
    gems = [
        ('بسته ۱۲۰ جم', 120, 19000, 1),
        ('بسته ۵۰۰ جم', 500, 69000, 2),
        ('بسته ۱۲۰۰ جم', 1200, 149000, 3),
    ]
    for title, amount, price, order in gems:
        GemPackage.objects.get_or_create(
            title=title,
            defaults={'gems': amount, 'price': price, 'is_active': True, 'sort_order': order},
        )
    digital = [
        ('بسته ۸۰۰ سی‌پی', 'cp', 89000, 1),
        ('بتل‌پس فصل جاری', 'battle_pass', 129000, 2),
    ]
    for title, kind, price, order in digital:
        DigitalProduct.objects.get_or_create(
            title=title,
            defaults={
                'kind': kind,
                'game_name': 'Call of Duty Mobile',
                'price': price,
                'is_active': True,
                'sort_order': order,
                'description': 'شارژ توسط اپراتور کیل‌باکس پس از ورود به اکانت.',
            },
        )
    physical = [
        ('دسته بازی کیل‌باکس', 'joystick-kb', 1850000, 8, 1),
        ('تیشرت عملیات ویژه', 'ops-tee', 420000, 20, 2),
    ]
    for title, slug, price, stock, order in physical:
        PhysicalProduct.objects.get_or_create(
            slug=slug,
            defaults={
                'title': title,
                'price': price,
                'stock': stock,
                'is_active': True,
                'sort_order': order,
                'description': 'ارسال پستی به سراسر کشور.',
            },
        )


def seed_backward(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ('shop', '0001_initial_shop'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_backward),
    ]
