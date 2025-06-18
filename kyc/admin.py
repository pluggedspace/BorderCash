from django.contrib import admin

from app.models import UserProfile
from .models import KYCRequest


class KYCRequestAdmin(admin.ModelAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = UserProfile.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    pass


admin.site.register(KYCRequest, KYCRequestAdmin)


