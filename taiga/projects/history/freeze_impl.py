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

from functools import partial
from django.db.models.loading import get_model
from django.contrib.contenttypes.models import ContentType
from taiga.base.utils.iterators import as_tuple
from taiga.base.utils.iterators import as_dict
from taiga.mdrender.service import render as mdrender

import os

####################
# Values
####################

@as_dict
def _get_generic_values(ids:tuple, *, typename=None, attr:str="name") -> tuple:
    app_label, model_name = typename.split(".", 1)
    content_type = ContentType.objects.get(app_label=app_label, model=model_name)
    model_cls = content_type.model_class()

    ids = filter(lambda x: x is not None, ids)
    qs = model_cls.objects.filter(pk__in=ids)
    for instance in qs:
        yield str(instance.pk), getattr(instance, attr)


@as_dict
def _get_users_values(ids:set) -> dict:
    user_model = get_model("users", "User")
    ids = filter(lambda x: x is not None, ids)
    qs = user_model.objects.filter(pk__in=tuple(ids))

    for user in qs:
        yield str(user.pk), user.get_full_name()


_get_us_status_values = partial(_get_generic_values, typename="projects.userstorystatus")
_get_task_status_values = partial(_get_generic_values, typename="projects.taskstatus")
_get_issue_status_values = partial(_get_generic_values, typename="projects.issuestatus")
_get_issue_type_values = partial(_get_generic_values, typename="projects.issuetype")
_get_role_values = partial(_get_generic_values, typename="users.role")
_get_points_values = partial(_get_generic_values, typename="projects.points")
_get_priority_values = partial(_get_generic_values, typename="projects.priority")
_get_severity_values = partial(_get_generic_values, typename="projects.severity")
_get_milestone_values = partial(_get_generic_values, typename="milestones.milestone")


def _common_users_values(diff):
    """
    Groups common values resolver logic of userstories,
    issues and tasks.
    """
    values = {}
    users = set()

    if "owner" in diff:
        users.update(diff["owner"])
    if "watchers" in diff:
        for ids in diff["watchers"]:
            if not ids:
                continue
            users.update(ids)
    if "assigned_to" in diff:
        users.update(diff["assigned_to"])
    if users:
        values["users"] = _get_users_values(users)

    return values


def milestone_values(diff):
    values = _common_users_values(diff)

    return values


def userstory_values(diff):
    values = _common_users_values(diff)

    if "status" in diff:
        values["status"] = _get_us_status_values(diff["status"])
    if "milestone" in diff:
        values["milestone"] = _get_milestone_values(diff["milestone"])
    if "points" in diff:
        points, roles = set(), set()

        for pointsentry in diff["points"]:
            if pointsentry is None:
                continue

            for role_id, point_id in pointsentry.items():
                points.add(point_id)
                roles.add(role_id)

        values["roles"] = _get_role_values(roles)
        values["points"] = _get_points_values(points)

    return values


def issue_values(diff):
    values = _common_users_values(diff)

    if "status" in diff:
        values["status"] = _get_issue_status_values(diff["status"])
    if "milestone" in diff:
        values["milestone"] = _get_milestone_values(diff["milestone"])
    if "priority" in diff:
        values["priority"] = _get_priority_values(diff["priority"])
    if "severity" in diff:
        values["severity"] = _get_severity_values(diff["severity"])
    if "type" in diff:
        values["issue_type"] = _get_issue_type_values(diff["type"])

    return values


def task_values(diff):
    values = _common_users_values(diff)

    if "status" in diff:
        values["status"] = _get_task_status_values(diff["status"])
    if "milestone" in diff:
        values["milestone"] = _get_milestone_values(diff["milestone"])

    return values


def wikipage_values(diff):
    values = _common_users_values(diff)
    return values


####################
# Freezes
####################


@as_tuple
def extract_attachments(obj) -> list:
    for attach in obj.attachments.all():
        yield {"id": attach.id,
               "filename": os.path.basename(attach.attached_file.name),
               "description": attach.description,
               "is_deprecated": attach.is_deprecated,
               "description": attach.description,
               "order": attach.order}


def milestone_freezer(milestone) -> dict:
    snapshot = {
        "name": milestone.name,
        "slug": milestone.slug,
        "owner": milestone.owner_id,
        "estimated_start": milestone.estimated_start,
        "estimated_finish": milestone.estimated_finish,
        "closed": milestone.closed,
        "disponibility": milestone.disponibility
    }

    return snapshot

def userstory_freezer(us) -> dict:
    rp_cls = get_model("userstories", "RolePoints")
    rpqsd = rp_cls.objects.filter(user_story=us)

    points = {}
    for rp in rpqsd:
        points[str(rp.role_id)] = rp.points_id

    snapshot = {
        "ref": us.ref,
        "owner": us.owner_id,
        "status": us.status_id,
        "is_closed": us.is_closed,
        "finish_date": us.finish_date,
        "order": us.order,
        "subject": us.subject,
        "description": us.description,
        "description_html": mdrender(us.project, us.description),
        "assigned_to": us.assigned_to_id,
        "milestone": us.milestone_id,
        "client_requirement": us.client_requirement,
        "team_requirement": us.team_requirement,
        "watchers": [x.id for x in us.watchers.all()],
        "attachments": extract_attachments(us),
        "tags": us.tags,
        "points": points,
        "from_issue": us.generated_from_issue_id,
    }

    return snapshot


def issue_freezer(issue) -> dict:
    snapshot = {
        "ref": issue.ref,
        "owner": issue.owner_id,
        "status": issue.status_id,
        "priority": issue.priority_id,
        "severity": issue.severity_id,
        "type": issue.type_id,
        "milestone": issue.milestone_id,
        "subject": issue.subject,
        "description": issue.description,
        "description_html": mdrender(issue.project, issue.description),
        "assigned_to": issue.assigned_to_id,
        "watchers": [x.pk for x in issue.watchers.all()],
        "attachments": extract_attachments(issue),
        "tags": issue.tags,
    }

    return snapshot


def task_freezer(task) -> dict:
    snapshot = {
        "ref": task.ref,
        "owner": task.owner_id,
        "status": task.status_id,
        "milestone": task.milestone_id,
        "subject": task.subject,
        "description": task.description,
        "description_html": mdrender(task.project, task.description),
        "assigned_to": task.assigned_to_id,
        "watchers": [x.pk for x in task.watchers.all()],
        "attachments": extract_attachments(task),
        "tags": task.tags,
        "user_story": task.user_story_id,
        "is_iocaine": task.is_iocaine,
    }

    return snapshot


def wikipage_freezer(wiki) -> dict:
    snapshot = {
        "slug": wiki.slug,
        "owner": wiki.owner_id,
        "content": wiki.content,
        "content_html": mdrender(wiki.project, wiki.content),
        "watchers": [x.pk for x in wiki.watchers.all()],
        "attachments": extract_attachments(wiki),
    }

    return snapshot
