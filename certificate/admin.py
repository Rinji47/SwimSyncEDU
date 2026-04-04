from django.contrib import admin

from certificate.models import CompletionCertificate


@admin.register(CompletionCertificate)
class CompletionCertificateAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'trainer', 'issued_at')
    search_fields = ('user__username', 'user__full_name', 'trainer__username', 'trainer__full_name')
    list_select_related = ('user', 'trainer')
