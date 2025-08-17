from django.contrib import admin

from publishers.models import PublisherInvitation, PublisherProfile, PublishingAgreement

admin.site.register(PublisherInvitation)
admin.site.register(PublisherProfile)
admin.site.register(PublishingAgreement)
