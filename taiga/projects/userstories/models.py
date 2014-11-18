# Copyright (C) 2014 Andrey Antukh <niwi@niwi.be>
# Copyright (C) 2014 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014 David Barragán <bameda@dbarragan.com>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.db import models
from django.contrib.contenttypes import generic
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

from djorm_pgarray.fields import TextArrayField

from taiga.projects.occ import OCCModelMixin
from taiga.projects.notifications.mixins import WatchedModelMixin
from taiga.projects.mixins.blocked import BlockedMixin
from taiga.base.tags import TaggedMixin


class RolePoints(models.Model):
    user_story = models.ForeignKey("UserStory", null=False, blank=False,
                                   related_name="role_points",
                                   verbose_name=_("user story"))
    role = models.ForeignKey("users.Role", null=False, blank=False,
                             related_name="role_points",
                             verbose_name=_("role"))
    points = models.ForeignKey("projects.Points", null=True, blank=False,
                               related_name="role_points",
                               verbose_name=_("points"))

    class Meta:
        verbose_name = "role points"
        verbose_name_plural = "role points"
        unique_together = ("user_story", "role")
        ordering = ["user_story", "role"]

    def __str__(self):
        return "{}: {}".format(self.role.name, self.points.name)


class UserStory(OCCModelMixin, WatchedModelMixin, BlockedMixin, TaggedMixin, models.Model):
    ref = models.BigIntegerField(db_index=True, null=True, blank=True, default=None,
                                 verbose_name=_("ref"))
    milestone = models.ForeignKey("milestones.Milestone", null=True, blank=True,
                                  default=None, related_name="user_stories",
                                  on_delete=models.SET_NULL, verbose_name=_("milestone"))
    project = models.ForeignKey("projects.Project", null=False, blank=False,
                                related_name="user_stories", verbose_name=_("project"))
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              related_name="owned_user_stories", verbose_name=_("owner"),
                              on_delete=models.SET_NULL)
    status = models.ForeignKey("projects.UserStoryStatus", null=True, blank=True,
                               related_name="user_stories", verbose_name=_("status"),
                               on_delete=models.SET_NULL)
    is_closed = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False, null=False, blank=True,
                                      verbose_name=_("archived"))
    points = models.ManyToManyField("projects.Points", null=False, blank=False,
                                    related_name="userstories", through="RolePoints",
                                    verbose_name=_("points"))

    backlog_order = models.IntegerField(null=False, blank=False, default=10000,
                                        verbose_name=_("backlog order"))
    sprint_order = models.IntegerField(null=False, blank=False, default=10000,
                                       verbose_name=_("sprint order"))
    kanban_order = models.IntegerField(null=False, blank=False, default=10000,
                                       verbose_name=_("sprint order"))

    created_date = models.DateTimeField(null=False, blank=False,
                                        verbose_name=_("created date"),
                                        default=timezone.now)
    modified_date = models.DateTimeField(null=False, blank=False,
                                         verbose_name=_("modified date"))
    finish_date = models.DateTimeField(null=True, blank=True,
                                       verbose_name=_("finish date"))
    subject = models.TextField(null=False, blank=False,
                               verbose_name=_("subject"))
    description = models.TextField(null=False, blank=True, verbose_name=_("description"))
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True,
                                    default=None, related_name="userstories_assigned_to_me",
                                    verbose_name=_("assigned to"))
    client_requirement = models.BooleanField(default=False, null=False, blank=True,
                                             verbose_name=_("is client requirement"))
    team_requirement = models.BooleanField(default=False, null=False, blank=True,
                                           verbose_name=_("is team requirement"))
    attachments = generic.GenericRelation("attachments.Attachment")
    generated_from_issue = models.ForeignKey("issues.Issue", null=True, blank=True,
                                             on_delete=models.SET_NULL,
                                             related_name="generated_user_stories",
                                             verbose_name=_("generated from issue"))
    external_reference = TextArrayField(default=None, verbose_name=_("external reference"))
    _importing = None

    class Meta:
        verbose_name = "user story"
        verbose_name_plural = "user stories"
        ordering = ["project", "backlog_order", "ref"]

    def save(self, *args, **kwargs):
        if not self._importing or not self.modified_date:
            self.modified_date = timezone.now()

        if not self.status:
            self.status = self.project.default_us_status

        super().save(*args, **kwargs)

    def __str__(self):
        return "({1}) {0}".format(self.ref, self.subject)

    def __repr__(self):
        return "<UserStory %s>" % (self.id)

    def get_role_points(self):
        return self.role_points

    def get_total_points(self):
        not_null_role_points = self.role_points.select_related("points").\
            exclude(points__value__isnull=True)

        #If we only have None values the sum should be None
        if not not_null_role_points:
            return None

        total = 0.0
        for rp in not_null_role_points:
            total += rp.points.value

        return total
