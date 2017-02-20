# -*- coding: utf-8 -*-
# Copyright (C) 2014-2016 Andrey Antukh <niwi@niwi.nz>
# Copyright (C) 2014-2016 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014-2016 David Barragán <bameda@dbarragan.com>
# Copyright (C) 2014-2016 Alejandro Alonso <alejandro.alonso@kaleidos.net>
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

from django.apps import apps
from django.db import transaction

from django.utils.translation import ugettext as _
from django.http import HttpResponse

from taiga.base import filters as base_filters
from taiga.base import exceptions as exc
from taiga.base import response
from taiga.base import status
from taiga.base.decorators import list_route
from taiga.base.api.mixins import BlockedByProjectMixin
from taiga.base.api import ModelCrudViewSet
from taiga.base.api import ModelListViewSet
from taiga.base.api.utils import get_object_or_404
from taiga.base.utils import json

from taiga.projects.history.mixins import HistoryResourceMixin
from taiga.projects.history.services import take_snapshot
from taiga.projects.milestones.models import Milestone
from taiga.projects.mixins.by_ref import ByRefMixin
from taiga.projects.models import Project, UserStoryStatus
from taiga.projects.notifications.mixins import WatchedResourceMixin
from taiga.projects.notifications.mixins import WatchersViewSetMixin
from taiga.projects.occ import OCCResourceMixin
from taiga.projects.tagging.api import TaggedResourceMixin
from taiga.projects.votes.mixins.viewsets import VotedResourceMixin
from taiga.projects.votes.mixins.viewsets import VotersViewSetMixin
from taiga.projects.userstories.utils import attach_extra_info

from . import filters
from . import models
from . import permissions
from . import serializers
from . import services
from . import validators


class UserStoryViewSet(OCCResourceMixin, VotedResourceMixin, HistoryResourceMixin, WatchedResourceMixin,
                       ByRefMixin, TaggedResourceMixin, BlockedByProjectMixin, ModelCrudViewSet):
    validator_class = validators.UserStoryValidator
    queryset = models.UserStory.objects.all()
    permission_classes = (permissions.UserStoryPermission,)
    filter_backends = (base_filters.CanViewUsFilterBackend,
                       filters.EpicFilter,
                       base_filters.OwnersFilter,
                       base_filters.AssignedToFilter,
                       base_filters.StatusesFilter,
                       base_filters.TagsFilter,
                       base_filters.WatchersFilter,
                       base_filters.QFilter,
                       base_filters.CreatedDateFilter,
                       base_filters.ModifiedDateFilter,
                       base_filters.FinishDateFilter,
                       base_filters.MilestoneEstimatedStartFilter,
                       base_filters.MilestoneEstimatedFinishFilter,
                       base_filters.OrderByFilterMixin)
    filter_fields = ["project",
                     "project__slug",
                     "milestone",
                     "milestone__isnull",
                     "is_closed",
                     "status__is_archived",
                     "status__is_closed"]
    order_by_fields = ["backlog_order",
                       "sprint_order",
                       "kanban_order",
                       "epic_order",
                       "total_voters"]

    def get_serializer_class(self, *args, **kwargs):
        if self.action in ["retrieve", "by_ref"]:
            return serializers.UserStoryNeighborsSerializer

        if self.action == "list":
            return serializers.UserStoryListSerializer

        return serializers.UserStorySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.select_related("milestone",
                               "project",
                               "status",
                               "owner",
                               "assigned_to",
                               "generated_from_issue")

        include_attachments = "include_attachments" in self.request.QUERY_PARAMS
        include_tasks = "include_tasks" in self.request.QUERY_PARAMS

        epic_id = self.request.QUERY_PARAMS.get("epic", None)
        # We can be filtering by more than one epic so epic_id can consist
        # of different ids separete by comma. In that situation we will use
        # only the first
        if epic_id is not None:
            epic_id = epic_id.split(",")[0]

        qs = attach_extra_info(qs, user=self.request.user,
                               include_attachments=include_attachments,
                               include_tasks=include_tasks,
                               epic_id=epic_id)

        return qs

    def pre_conditions_on_save(self, obj):
        super().pre_conditions_on_save(obj)

        if obj.milestone and obj.milestone.project != obj.project:
            raise exc.PermissionDenied(_("You don't have permissions to set this sprint "
                                         "to this user story."))

        if obj.status and obj.status.project != obj.project:
            raise exc.PermissionDenied(_("You don't have permissions to set this status "
                                         "to this user story."))

    """
    Updating some attributes of the userstory can affect the ordering in the backlog, kanban or taskboard
    These three methods generate a key for the user story and can be used to be compared before and after
    saving
    If there is any difference it means an extra ordering update must be done
    """
    def _backlog_order_key(self, obj):
        return "{}-{}".format(obj.project_id, obj.backlog_order)

    def _kanban_order_key(self, obj):
        return "{}-{}-{}".format(obj.project_id, obj.status_id, obj.kanban_order)

    def _sprint_order_key(self, obj):
        return "{}-{}-{}".format(obj.project_id, obj.milestone_id, obj.sprint_order)

    def pre_save(self, obj):
        # This is very ugly hack, but having
        # restframework is the only way to do it.
        #
        # NOTE: code moved as is from serializer
        #       to api because is not serializer logic.
        related_data = getattr(obj, "_related_data", {})
        self._role_points = related_data.pop("role_points", None)

        if not obj.id:
            obj.owner = self.request.user
        else:
            self._old_backlog_order_key = self._backlog_order_key(self.get_object())
            self._old_kanban_order_key = self._kanban_order_key(self.get_object())
            self._old_sprint_order_key = self._sprint_order_key(self.get_object())

        super().pre_save(obj)

    def _reorder_if_needed(self, obj, old_order_key, order_key, order_attr,
                           project, status=None, milestone=None):
        # Executes the extra ordering if there is a difference in the  ordering keys
        if old_order_key != order_key:
            extra_orders = json.loads(self.request.META.get("HTTP_SET_ORDERS", "{}"))
            data = [{"us_id": obj.id, "order": getattr(obj, order_attr)}]
            for id, order in extra_orders.items():
                data.append({"us_id": int(id), "order": order})

            return services.update_userstories_order_in_bulk(data,
                                                             order_attr,
                                                             project,
                                                             status=status,
                                                             milestone=milestone)
        return {}

    def post_save(self, obj, created=False):
        if not created:
            # Let's reorder the related stuff after edit the element
            orders_updated = {}
            updated = self._reorder_if_needed(obj,
                                              self._old_backlog_order_key,
                                              self._backlog_order_key(obj),
                                              "backlog_order",
                                              obj.project)
            orders_updated.update(updated)
            updated = self._reorder_if_needed(obj,
                                              self._old_kanban_order_key,
                                              self._kanban_order_key(obj),
                                              "kanban_order",
                                              obj.project,
                                              status=obj.status)
            orders_updated.update(updated)
            updated = self._reorder_if_needed(obj,
                                              self._old_sprint_order_key,
                                              self._sprint_order_key(obj),
                                              "sprint_order",
                                              obj.project,
                                              milestone=obj.milestone)
            orders_updated.update(updated)
            self.headers["Taiga-Info-Order-Updated"] = json.dumps(orders_updated)

        # Code related to the hack of pre_save method.
        # Rather, this is the continuation of it.
        if self._role_points:
            Points = apps.get_model("projects", "Points")
            RolePoints = apps.get_model("userstories", "RolePoints")

            for role_id, points_id in self._role_points.items():
                try:
                    role_points = RolePoints.objects.get(role__id=role_id, user_story_id=obj.pk,
                                                         role__computable=True)
                except (ValueError, RolePoints.DoesNotExist):
                    raise exc.BadRequest({
                        "points": _("Invalid role id '{role_id}'").format(role_id=role_id)
                    })

                try:
                    role_points.points = Points.objects.get(id=points_id, project_id=obj.project_id)
                except (ValueError, Points.DoesNotExist):
                    raise exc.BadRequest({
                        "points": _("Invalid points id '{points_id}'").format(points_id=points_id)
                    })

                role_points.save()

        super().post_save(obj, created)

    @transaction.atomic
    def create(self, *args, **kwargs):
        response = super().create(*args, **kwargs)

        # Added comment to the origin (issue)
        if response.status_code == status.HTTP_201_CREATED and self.object.generated_from_issue:
            self.object.generated_from_issue.save()

            comment = _("Generating the user story #{ref} - {subject}")
            comment = comment.format(ref=self.object.ref, subject=self.object.subject)
            history = take_snapshot(self.object.generated_from_issue,
                                    comment=comment,
                                    user=self.request.user)

            self.send_notifications(self.object.generated_from_issue, history)

        return response

    def update(self, request, *args, **kwargs):
        self.object = self.get_object_or_none()
        project_id = request.DATA.get('project', None)

        if project_id and self.object and self.object.project.id != project_id:
            try:
                new_project = Project.objects.get(pk=project_id)
                self.check_permissions(request, "destroy", self.object)
                self.check_permissions(request, "create", new_project)

                sprint_id = request.DATA.get('milestone', None)
                if sprint_id is not None and new_project.milestones.filter(pk=sprint_id).count() == 0:
                    request.DATA['milestone'] = None

                status_id = request.DATA.get('status', None)
                if status_id is not None:
                    try:
                        old_status = self.object.project.us_statuses.get(pk=status_id)
                        new_status = new_project.us_statuses.get(slug=old_status.slug)
                        request.DATA['status'] = new_status.id
                    except UserStoryStatus.DoesNotExist:
                        request.DATA['status'] = new_project.default_us_status.id
            except Project.DoesNotExist:
                return response.BadRequest(_("The project doesn't exist"))

        return super().update(request, *args, **kwargs)

    @list_route(methods=["GET"])
    def filters_data(self, request, *args, **kwargs):
        project_id = request.QUERY_PARAMS.get("project", None)
        project = get_object_or_404(Project, id=project_id)

        filter_backends = self.get_filter_backends()
        statuses_filter_backends = (f for f in filter_backends if f != base_filters.StatusesFilter)
        assigned_to_filter_backends = (f for f in filter_backends if f != base_filters.AssignedToFilter)
        owners_filter_backends = (f for f in filter_backends if f != base_filters.OwnersFilter)
        epics_filter_backends = (f for f in filter_backends if f != filters.EpicFilter)

        queryset = self.get_queryset()
        querysets = {
            "statuses": self.filter_queryset(queryset, filter_backends=statuses_filter_backends),
            "assigned_to": self.filter_queryset(queryset, filter_backends=assigned_to_filter_backends),
            "owners": self.filter_queryset(queryset, filter_backends=owners_filter_backends),
            "tags": self.filter_queryset(queryset),
            "epics": self.filter_queryset(queryset, filter_backends=epics_filter_backends)
        }
        return response.Ok(services.get_userstories_filters_data(project, querysets))

    @list_route(methods=["GET"])
    def csv(self, request):
        uuid = request.QUERY_PARAMS.get("uuid", None)
        if uuid is None:
            return response.NotFound()

        project = get_object_or_404(Project, userstories_csv_uuid=uuid)
        queryset = project.user_stories.all().order_by('ref')
        data = services.userstories_to_csv(project, queryset)
        csv_response = HttpResponse(data.getvalue(), content_type='application/csv; charset=utf-8')
        csv_response['Content-Disposition'] = 'attachment; filename="userstories.csv"'
        return csv_response

    @list_route(methods=["POST"])
    def bulk_create(self, request, **kwargs):
        validator = validators.UserStoriesBulkValidator(data=request.DATA)
        if validator.is_valid():
            data = validator.data
            project = Project.objects.get(id=data["project_id"])
            self.check_permissions(request, 'bulk_create', project)
            if project.blocked_code is not None:
                raise exc.Blocked(_("Blocked element"))

            user_stories = services.create_userstories_in_bulk(
                data["bulk_stories"], project=project, owner=request.user,
                status_id=data.get("status_id") or project.default_us_status_id,
                callback=self.post_save, precall=self.pre_save)

            user_stories = self.get_queryset().filter(id__in=[i.id for i in user_stories])
            for user_story in user_stories:
                self.persist_history_snapshot(obj=user_story)

            user_stories_serialized = self.get_serializer_class()(user_stories, many=True)

            return response.Ok(user_stories_serialized.data)
        return response.BadRequest(validator.errors)

    @list_route(methods=["POST"])
    def bulk_update_milestone(self, request, **kwargs):
        validator = validators.UpdateMilestoneBulkValidator(data=request.DATA)
        if not validator.is_valid():
            return response.BadRequest(validator.errors)

        data = validator.data
        project = get_object_or_404(Project, pk=data["project_id"])
        milestone = get_object_or_404(Milestone, pk=data["milestone_id"])

        self.check_permissions(request, "bulk_update_milestone", project)

        services.update_userstories_milestone_in_bulk(data["bulk_stories"], milestone)
        services.snapshot_userstories_in_bulk(data["bulk_stories"], request.user)

        return response.NoContent()

    def _bulk_update_order(self, order_field, request, **kwargs):
        validator = validators.UpdateUserStoriesOrderBulkValidator(data=request.DATA)
        if not validator.is_valid():
            return response.BadRequest(validator.errors)

        data = validator.data
        project = get_object_or_404(Project, pk=data["project_id"])
        status = None
        status_id = data.get("status_id", None)
        if status_id is not None:
            status = get_object_or_404(UserStoryStatus, pk=status_id)

        milestone = None
        milestone_id = data.get("milestone_id", None)
        if milestone_id is not None:
            milestone = get_object_or_404(Milestone, pk=milestone_id)

        self.check_permissions(request, "bulk_update_order", project)
        if project.blocked_code is not None:
            raise exc.Blocked(_("Blocked element"))

        ret = services.update_userstories_order_in_bulk(data["bulk_stories"],
                                                        order_field,
                                                        project,
                                                        status=status,
                                                        milestone=milestone)
        return response.Ok(ret)

    @list_route(methods=["POST"])
    def bulk_update_backlog_order(self, request, **kwargs):
        return self._bulk_update_order("backlog_order", request, **kwargs)

    @list_route(methods=["POST"])
    def bulk_update_sprint_order(self, request, **kwargs):
        return self._bulk_update_order("sprint_order", request, **kwargs)

    @list_route(methods=["POST"])
    def bulk_update_kanban_order(self, request, **kwargs):
        return self._bulk_update_order("kanban_order", request, **kwargs)


class UserStoryVotersViewSet(VotersViewSetMixin, ModelListViewSet):
    permission_classes = (permissions.UserStoryVotersPermission,)
    resource_model = models.UserStory


class UserStoryWatchersViewSet(WatchersViewSetMixin, ModelListViewSet):
    permission_classes = (permissions.UserStoryWatchersPermission,)
    resource_model = models.UserStory
