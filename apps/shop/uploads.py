def gem_image_upload_to(instance, filename):
    return f'shop/gems/{instance.pk or "new"}-{filename}'


def digital_image_upload_to(instance, filename):
    return f'shop/digital/{instance.pk or "new"}-{filename}'


def listing_image_upload_to(instance, filename):
    return f'shop/listings/{instance.listing_id}/{filename}'


def physical_image_upload_to(instance, filename):
    return f'shop/physical/{instance.pk or "new"}-{filename}'
