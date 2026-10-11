from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateSupportStorage(FileSystemStorage):
    """Filesystem storage for support screenshots without a public media URL."""

    def __init__(self, location=None):
        super().__init__(location=location or settings.PRIVATE_SUPPORT_ROOT, base_url=None)

    def url(self, name):
        raise ValueError("Support attachments are private and must be served through the authorized view.")
