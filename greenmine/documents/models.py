# -* coding: utf-8 -*-
from django.db import models

from greenmine.base.utils.slug import slugify_uniquely as slugify
from greenmine.base.fields import DictField


class Document(models.Model):
    slug = models.SlugField(unique=True, max_length=200, null=False, blank=True,
                verbose_name=_('slug'))
    title = models.CharField(max_length=150, null=False, blank=False,
                verbose_name=_('title'))
    description = models.TextField(null=False, blank=True,
                verbose_name=_('description'))
    created_date = models.DateTimeField(auto_now_add=True, null=False, blank=False,
                verbose_name=_('created date'))
    modified_date = models.DateTimeField(auto_now=True, null=False, blank=False,
                verbose_name=_('modified date'))
    project = models.ForeignKey('scrum.Project', null=False, blank=False,
                related_name='documents',
                verbose_name=_('project'))
    owner = models.ForeignKey('base.User', null=False, blank=False,
                related_name='owned_documents',
                verbose_name=_('owner'))
    attached_file = models.FileField(max_length=1000, null=True, blank=True,
                upload_to='documents',
                verbose_name=_('attached_file'))
    tags = DictField(null=False, blank=True,
                verbose_name=_('tags'))

    class Meta:
        verbose_name = u'document'
        verbose_name_plural = u'document'
        ordering = ['project', 'title', 'id']
        permissions = (
            ('can_download_from_my_projects', 'Can download the documents from my projects'),
            ('can_download_from_other_projects', 'Can download the documents from other projects'),
            ('can_change_owned_documents', 'Can modify owned documents'),
            ('can_view_documents', 'Can modify owned documents'),
        )

    def __unicode__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title, self.__class__)
        super(Document, self).save(*args, **kwargs)

