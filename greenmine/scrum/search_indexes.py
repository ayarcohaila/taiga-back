# -* coding: utf-8 -*-
from haystack import indexes
from greenmine.scrum.models import UserStory, Task


class UserStoryIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True, template_name='search/indexes/userstory_text.txt')

    def get_model(self):
        return UserStory

    def index_queryset(self):
        return self.get_model().objects.all()


class TaskIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True, template_name='search/indexes/task_text.txt')

    def get_model(self):
        return Task

    def index_queryset(self):
        return self.get_model().objects.all()
