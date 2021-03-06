from django.conf import settings
from django.db import models

from django_sharding_library.fields import BigAutoField


def _get_primary_shards():
    """
    Returns the names of databases which make up the shards and have no primary.
    """
    return sorted(
        filter(
            lambda db: not settings.DATABASES[db].get('PRIMARY', None) and settings.DATABASES[db].get('SHARD_GROUP', None),
            settings.DATABASES.keys()
        )
    )


class ShardedByMixin(models.Model):
    """
    This mixin is intended to be used with the included `save_shard_handler` in order
    to save the shard to the object. This is done by registering it on the User's pre-save signal.
    Look at the signal's docstring for additional information.

    Note: requires the use of `cls.shard_group`
    """
    django_sharding__shard_field = 'shard'
    django_sharding__stores_shard = True

    SHARD_CHOICES = ((i, i) for i in _get_primary_shards())

    shard = models.CharField(max_length=120, blank=True, null=True, choices=SHARD_CHOICES)

    class Meta:
        abstract = True


class TableStrategyModel(models.Model):
    """
    A model for use with the TableStrategy in order to generate ids using an
    autoincrimenting field. To use this, simply inherit from this class and give
    the model a more meaningful name e.g. InvoiceIDs.
    """
    id = BigAutoField(primary_key=True)
    stub = models.NullBooleanField(null=True, default=True, unique=True)

    class Meta:
        abstract = True


class ShardStorageModel(models.Model):
    """
    A model for storing shards.
    """
    SHARD_CHOICES = ((i, i) for i in _get_primary_shards())

    shard = models.CharField(max_length=120, choices=SHARD_CHOICES)
    shard_key = models.CharField(primary_key=True, max_length=120)

    class Meta:
        abstract = True


class ShardLookupQuerySet(models.QuerySet):
    def bulk_create(self, objs, batch_size=None):
        objs = list(objs)
        for obj in objs:
            if obj._state.db is None:
                obj._state.db = self._db

        return super().bulk_create(objs, batch_size)


class ShardLookupBaseModel(models.Model):
    """
    Unfortunatly when you call `model.objects.using(db).create(...) Django
    ignores the `db` passed to using and still tries to access the router.

    This can lead to many unnecesarry calls as well as circular resolution
    of the model.

    This is one way of solving this problem.
    """
    objects = ShardLookupQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, **kwargs):
        if not self._state.db:
            self._state.db = kwargs["using"]

        return super().save(**kwargs)
