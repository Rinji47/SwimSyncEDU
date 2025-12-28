from django.db import models

# Create your models here.
class Pool(models.Model):
    pool_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    address = models.TextField()
    capacity = models.IntegerField()
    image_url = models.URLField(max_length=200, blank=True, null=True)
    coordinates = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name