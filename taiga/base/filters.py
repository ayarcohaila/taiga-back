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
import operator
from functools import reduce

from django.db.models import Q
from django.db.models.sql.where import ExtraWhere, OR

from rest_framework import filters

from taiga.base import tags


class QueryParamsFilterMixin(filters.BaseFilterBackend):
    _special_values_dict = {
        'true': True,
        'false': False,
        'null': None,
    }

    def filter_queryset(self, request, queryset, view):
        query_params = {}

        if not hasattr(view, "filter_fields"):
            return queryset

        for field in view.filter_fields:
            if isinstance(field, (tuple, list)):
                param_name, field_name = field
            else:
                param_name, field_name = field, field

            if param_name in request.QUERY_PARAMS:
                field_data = request.QUERY_PARAMS[param_name]
                if field_data in self._special_values_dict:
                    query_params[field_name] = self._special_values_dict[field_data]
                else:
                    query_params[field_name] = field_data

        if query_params:
            queryset = queryset.filter(**query_params)

        return queryset


class OrderByFilterMixin(QueryParamsFilterMixin):
    order_by_query_param = "order_by"

    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)
        order_by_fields = getattr(view, "order_by_fields", None)

        raw_fieldname = request.QUERY_PARAMS.get(self.order_by_query_param, None)
        if not raw_fieldname or not order_by_fields:
            return queryset

        if raw_fieldname.startswith("-"):
            field_name = raw_fieldname[1:]
        else:
            field_name = raw_fieldname

        if field_name not in order_by_fields:
            return queryset

        return super().filter_queryset(request, queryset.order_by(raw_fieldname), view)


class FilterBackend(OrderByFilterMixin):
    """
    Default filter backend.
    """
    pass


class PermissionBasedFilterBackend(FilterBackend):
    permission = None

    def filter_queryset(self, request, queryset, view):
        # TODO: Make permissions aware of members permissions, now only check membership.
        qs = queryset

        if request.user.is_authenticated() and request.user.is_superuser:
            qs = qs
        elif request.user.is_authenticated():
            qs = qs.filter(Q(project__owner=request.user) |
                           Q(project__members=request.user) |
                           Q(project__is_private=False))
            qs.query.where.add(ExtraWhere(["projects_project.public_permissions @> ARRAY['{}']".format(self.permission)], []), OR)
        else:
            qs = qs.filter(project__is_private=False)
            qs.query.where.add(ExtraWhere(["projects_project.anon_permissions @> ARRAY['{}']".format(self.permission)], []), OR)

        return super().filter_queryset(request, qs.distinct(), view)


class CanViewProjectFilterBackend(PermissionBasedFilterBackend):
    permission = "view_project"


class CanViewUsFilterBackend(PermissionBasedFilterBackend):
    permission = "view_us"


class CanViewIssuesFilterBackend(PermissionBasedFilterBackend):
    permission = "view_issues"


class CanViewTasksFilterBackend(PermissionBasedFilterBackend):
    permission = "view_tasks"


class CanViewWikiPagesFilterBackend(PermissionBasedFilterBackend):
    permission = "view_wiki_pages"


class CanViewWikiLinksFilterBackend(PermissionBasedFilterBackend):
    permission = "view_wiki_links"


class CanViewMilestonesFilterBackend(PermissionBasedFilterBackend):
    permission = "view_milestones"

class PermissionBasedAttachmentFilterBackend(FilterBackend):
    permission = None

    def filter_queryset(self, request, queryset, view):
        # TODO: Make permissions aware of members permissions, now only check membership.
        qs = queryset

        if request.user.is_authenticated() and request.user.is_superuser:
            qs = qs
        elif request.user.is_authenticated():
            qs = qs.filter(Q(project__owner=request.user) |
                           Q(project__members=request.user) |
                           Q(project__is_private=False))
            qs.query.where.add(ExtraWhere(["projects_project.public_permissions @> ARRAY['{}']".format(self.permission)], []), OR)
        else:
            qs = qs.filter(project__is_private=False)
            qs.query.where.add(ExtraWhere(["projects_project.anon_permissions @> ARRAY['{}']".format(self.permission)], []), OR)

        ct = view.get_content_type()
        qs = qs.filter(content_type=ct)

        return super().filter_queryset(request, qs.distinct(), view)


class CanViewUserStoryAttachmentFilterBackend(PermissionBasedAttachmentFilterBackend):
    permission = "view_us"


class CanViewTaskAttachmentFilterBackend(PermissionBasedAttachmentFilterBackend):
    permission = "view_tasks"


class CanViewIssueAttachmentFilterBackend(PermissionBasedAttachmentFilterBackend):
    permission = "view_issues"


class CanViewWikiAttachmentFilterBackend(PermissionBasedAttachmentFilterBackend):
    permission = "view_wiki_pages"


class CanViewProjectObjFilterBackend(FilterBackend):
    def filter_queryset(self, request, queryset, view):
        qs = queryset

        if request.user.is_authenticated() and request.user.is_superuser:
            qs = qs
        elif request.user.is_authenticated():
            qs = qs.filter(Q(owner=request.user) |
                           Q(members=request.user) |
                           Q(is_private=False))
            qs.query.where.add(ExtraWhere(["projects_project.public_permissions @> ARRAY['view_project']"], []), OR)
        else:
            qs = qs.filter(is_private=False)
            qs.query.where.add(ExtraWhere(["projects_project.anon_permissions @> ARRAY['view_project']"], []), OR)

        return super().filter_queryset(request, qs.distinct(), view)


class IsProjectMemberFilterBackend(FilterBackend):
    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)
        user = request.user

        if user.is_authenticated():
            queryset = queryset.filter(Q(project__members=request.user) |
                                       Q(project__owner=request.user))
        return super().filter_queryset(request, queryset.distinct(), view)


class TagsFilter(FilterBackend):
    def __init__(self, filter_name='tags'):
        self.filter_name = filter_name

    def _get_tags_queryparams(self, params):
        return params.get(self.filter_name, "")

    def filter_queryset(self, request, queryset, view):
        query_tags = self._get_tags_queryparams(request.QUERY_PARAMS)
        if query_tags:
            queryset = tags.filter(queryset, contains=query_tags)

        return super().filter_queryset(request, queryset, view)


class SearchFieldFilter(filters.SearchFilter):
    """Search filter that looks up the search param in the parameter named after the search field,
    that is: ?<search field>=... instead of looking for the search param: ?search=...
    This way you can search in a field-specific way.
    """
    def get_search_terms(self, request, field):
        params = request.QUERY_PARAMS.get(field, '')
        return params.replace(',', ' ').split()

    def filter_queryset(self, request, queryset, view):
        search_fields = getattr(view, "search_fields", None)
        if not search_fields:
            return queryset

        lookups = dict((self.construct_search(field), self.get_search_terms(request, field))
                       for field in search_fields)

        for lookup, values in lookups.items():
            or_queries = [Q(**{lookup: value}) for value in values]
            if or_queries:
                queryset = queryset.filter(reduce(operator.or_, or_queries))

        return queryset
