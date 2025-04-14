from django.db import models

class Song(models.Model):
    title = models.CharField(max_length=255)
    audio_file = models.FileField(upload_to='songs/')

    def __str__(self):
        return self.title

class Fingerprint(models.Model):
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    hash = models.CharField(max_length=20, db_index=True)
    offset = models.IntegerField()
