from django.contrib.auth.models import User
from django.db import models

from pii_shield.models import PIIModel
from pii_shield.sync import register_model


@register_model
class Address(PIIModel):
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.street}, {self.city}, {self.country}"


@register_model
class UserProfile(PIIModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date_of_birth = models.DateField()
    phone_number = models.CharField(max_length=20)
    address = models.ForeignKey(
        Address, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"Profile for {self.user.username}"
