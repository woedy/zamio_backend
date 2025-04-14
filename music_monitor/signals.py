# api/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Track
from dejavu import Dejavu
from dejavu_config import config

@receiver(post_save, sender=Track)
def fingerprint_on_upload(sender, instance, created, **kwargs):
    if created and not instance.fingerprinted:
        try:
            djv = Dejavu(config)
            djv.fingerprint_file(instance.audio_file.path)
            instance.fingerprinted = True
            instance.save()
            print(f"Auto-fingerprinted: {instance.title}")
        except Exception as e:
            print(f"Fingerprinting failed for {instance.title}: {e}")
