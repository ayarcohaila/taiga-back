# Copyright (C) 2015 Andrey Antukh <niwi@niwi.be>
# Copyright (C) 2015 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2015 David Barragán <bameda@dbarragan.com>
# Copyright (C) 2015 Anler Hernández <hello@anler.me>
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

import pytest
from django.core.urlresolvers import reverse

from .. import factories as f

pytestmark = pytest.mark.django_db


def test_like_project(client):
    user = f.UserFactory.create()
    project = f.create_project(owner=user)
    f.MembershipFactory.create(project=project, user=user, is_owner=True)
    url = reverse("projects-like", args=(project.id,))

    client.login(user)
    response = client.post(url)

    assert response.status_code == 200


def test_unlike_project(client):
    user = f.UserFactory.create()
    project = f.create_project(owner=user)
    f.MembershipFactory.create(project=project, user=user, is_owner=True)
    url = reverse("projects-unlike", args=(project.id,))

    client.login(user)
    response = client.post(url)

    assert response.status_code == 200


def test_list_project_fans(client):
    user = f.UserFactory.create()
    project = f.create_project(owner=user)
    f.MembershipFactory.create(project=project, user=user, is_owner=True)
    f.VoteFactory.create(content_object=project, user=user)
    url = reverse("project-fans-list", args=(project.id,))

    client.login(user)
    response = client.get(url)

    assert response.status_code == 200
    assert response.data[0]['id'] == user.id


def test_get_project_fan(client):
    user = f.UserFactory.create()
    project = f.create_project(owner=user)
    f.MembershipFactory.create(project=project, user=user, is_owner=True)
    vote = f.VoteFactory.create(content_object=project, user=user)
    url = reverse("project-fans-detail", args=(project.id, vote.user.id))

    client.login(user)
    response = client.get(url)

    assert response.status_code == 200
    assert response.data['id'] == vote.user.id


def test_get_project_likes(client):
    user = f.UserFactory.create()
    project = f.create_project(owner=user)
    f.MembershipFactory.create(project=project, user=user, is_owner=True)
    url = reverse("projects-detail", args=(project.id,))

    f.VotesFactory.create(content_object=project, count=5)

    client.login(user)
    response = client.get(url)

    assert response.status_code == 200
    assert response.data['likes'] == 5


def test_get_project_is_liked(client):
    user = f.UserFactory.create()
    project = f.create_project(owner=user)
    f.MembershipFactory.create(project=project, user=user, is_owner=True)
    f.VotesFactory.create(content_object=project)
    url_detail = reverse("projects-detail", args=(project.id,))
    url_like = reverse("projects-like", args=(project.id,))
    url_unlike = reverse("projects-unlike", args=(project.id,))

    client.login(user)

    response = client.get(url_detail)
    assert response.status_code == 200
    assert response.data['likes'] == 0
    assert response.data['is_liked'] == False

    response = client.post(url_like)
    assert response.status_code == 200

    response = client.get(url_detail)
    assert response.status_code == 200
    assert response.data['likes'] == 1
    assert response.data['is_liked'] == True

    response = client.post(url_unlike)
    assert response.status_code == 200

    response = client.get(url_detail)
    assert response.status_code == 200
    assert response.data['likes'] == 0
    assert response.data['is_liked'] == False
