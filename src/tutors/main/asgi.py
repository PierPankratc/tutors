"""
ASGI config for main project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os
from pathlib import Path
import sys

from django.core.asgi import get_asgi_application

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

application = get_asgi_application()

