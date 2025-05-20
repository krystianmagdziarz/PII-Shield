# PII-Shield

Django package for selective data synchronization between secure networks and DMZ.

## Overview

PII-Shield allows you to selectively synchronize sensitive user data from a secure internal network to a DMZ (demilitarized zone) for the duration of a user session. This is especially useful for applications that need to maintain strong security controls while still providing responsive user experiences.

Key features:

- Synchronize data only for active user sessions
- Automatic expiration of synchronized data
- Use Django ORM transparently with synchronized models
- Redis-based communication between secure and DMZ networks
- Support for both synchronous and asynchronous Django views

## Requirements

- Python 3.12+
- Django 5.2+
- Redis 7.0+
- PostgreSQL 13+ (recommended)

## Installation

Install via pip:

```bash
pip install pii-shield
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    'pii_shield',
]
```

Add the middleware:

```python
MIDDLEWARE = [
    # ...
    'pii_shield.middleware.PIIShieldMiddleware',
]
```

Configure databases:

```python
DATABASES = {
    'default': {
        # Main database in secure network
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'main_db',
        # ...
    },
    'frontend': {
        # Frontend database in DMZ
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'frontend_db',
        # ...
    }
}

# Add database router
DATABASE_ROUTERS = ['pii_shield.routers.PIIRouter']
```

Add PII Shield settings:

```python
PII_SHIELD = {
    # Redis connection settings
    'REDIS': {
        'host': 'localhost',
        'port': 6379,
        'password': None,
        'ssl': False,
    },

    # Data expiration settings
    'SESSION': {
        'timeout': 1800,  # 30 minutes
        'refresh_threshold': 300,  # 5 minutes
    },

    # More settings... (see documentation)
}
```

## Usage

Create models that inherit from `PIIModel`:

```python
from django.db import models
from pii_shield.models import PIIModel
from pii_shield.sync import register_model

@register_model
class UserProfile(PIIModel):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    date_of_birth = models.DateField()
    phone_number = models.CharField(max_length=20)
    address = models.TextField()
```

Use models as normal in your views. The middleware will automatically synchronize data as needed:

```python
def profile_view(request):
    # Data will be automatically synchronized before this view is called
    profile = UserProfile.objects.get(user=request.user)
    return render(request, 'profile.html', {'profile': profile})
```

Manually trigger synchronization when needed:

```python
from pii_shield import sync_data

def update_profile(request):
    profile = UserProfile.objects.get(user=request.user)
    # Update profile...
    profile.save()

    # Synchronize updated data
    sync_data(profile, request.session.session_key)

    return redirect('profile')
```

## Management Commands

Clean up expired data:

```bash
python manage.py cleanup_expired_data
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
