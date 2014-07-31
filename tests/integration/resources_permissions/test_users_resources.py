import pytest
from django.core.urlresolvers import reverse

from rest_framework.renderers import JSONRenderer

from taiga.users.serializers import UserSerializer
from taiga.users.models import User
from taiga.permissions.permissions import MEMBERS_PERMISSIONS, ANON_PERMISSIONS, USER_PERMISSIONS

from tests import factories as f
from tests.utils import helper_test_http_method, disconnect_signals, reconnect_signals

import json

pytestmark = pytest.mark.django_db


def setup_module(module):
    disconnect_signals()


def teardown_module(module):
    reconnect_signals()


@pytest.fixture
def data():
    m = type("Models", (object,), {})

    m.registered_user = f.UserFactory.create()
    m.other_user = f.UserFactory.create()
    m.superuser = f.UserFactory.create(is_superuser=True)

    return m


def test_user_retrieve(client, data):
    url = reverse('users-detail', kwargs={"pk": data.registered_user.pk})

    users = [
        None,
        data.registered_user,
        data.other_user,
        data.superuser,
    ]

    results = helper_test_http_method(client, 'get', url, None, users)
    assert results == [200, 200, 200, 200]


def test_user_update(client, data):
    url = reverse('users-detail', kwargs={"pk": data.registered_user.pk})

    users = [
        None,
        data.registered_user,
        data.other_user,
        data.superuser,
    ]

    user_data = UserSerializer(data.registered_user).data
    user_data["full_name"] = "test"
    user_data = JSONRenderer().render(user_data)
    results = helper_test_http_method(client, 'put', url, user_data, users)
    assert results == [401, 200, 403, 200]


def test_user_delete(client, data):
    url = reverse('users-detail', kwargs={"pk": data.registered_user.pk})

    users = [
        None,
        data.other_user,
        data.registered_user,
    ]

    results = helper_test_http_method(client, 'delete', url, None, users)
    assert results == [401, 403, 204]


def test_user_list(client, data):
    url = reverse('users-list')

    response = client.get(url)
    users_data = json.loads(response.content.decode('utf-8'))
    assert len(users_data) == 3
    assert response.status_code == 200

    client.login(data.registered_user)

    response = client.get(url)
    users_data = json.loads(response.content.decode('utf-8'))
    assert len(users_data) == 3
    assert response.status_code == 200

    client.login(data.other_user)

    response = client.get(url)
    users_data = json.loads(response.content.decode('utf-8'))
    assert len(users_data) == 3
    assert response.status_code == 200

    client.login(data.superuser)

    response = client.get(url)
    users_data = json.loads(response.content.decode('utf-8'))
    assert len(users_data) == 3
    assert response.status_code == 200


def test_user_create(client, data):
    url = reverse('users-list')

    users = [
        None,
        data.registered_user,
        data.other_user,
        data.superuser,
    ]

    create_data = json.dumps({
        "username": "test",
        "full_name": "test",
    })
    results = helper_test_http_method(client, 'post', url, create_data, users, lambda: User.objects.filter(username="test").delete())
    assert results == [201, 201, 201, 201]


def test_user_patch(client, data):
    url = reverse('users-detail', kwargs={"pk": data.registered_user.pk})

    users = [
        None,
        data.registered_user,
        data.other_user,
        data.superuser,
    ]

    patch_data = json.dumps({"full_name": "test"})
    results = helper_test_http_method(client, 'patch', url, patch_data, users)
    assert results == [401, 200, 403, 200]

def test_user_action_change_password(client, data):
    url = reverse('users-change-password')

    data.registered_user.set_password("test-current-password")
    data.registered_user.save()
    data.other_user.set_password("test-current-password")
    data.other_user.save()
    data.superuser.set_password("test-current-password")
    data.superuser.save()

    users = [
        None,
        data.registered_user,
        data.other_user,
        data.superuser,
    ]


    patch_data = json.dumps({"current_password": "test-current-password", "password": "test-password"})
    results = helper_test_http_method(client, 'post', url, patch_data, users)
    assert results == [401, 204, 204, 204]

def test_user_action_change_password_from_recovery(client, data):
    url = reverse('users-change-password-from-recovery')

    new_user = f.UserFactory(token="test-token")

    def reset_token():
        new_user.token = "test-token"
        new_user.save()

    users = [
        None,
        data.registered_user,
        data.other_user,
        data.superuser,
    ]

    patch_data = json.dumps({"password": "test-password", "token": "test-token"})
    results = helper_test_http_method(client, 'post', url, patch_data, users, reset_token)
    assert results == [204, 204, 204, 204]

def test_user_action_password_recovery(client, data):
    url = reverse('users-password-recovery')

    new_user = f.UserFactory.create(username="test")

    users = [
        None,
        data.registered_user,
        data.other_user,
        data.superuser,
    ]

    patch_data = json.dumps({"username": "test"})
    results = helper_test_http_method(client, 'post', url, patch_data, users)
    assert results == [200, 200, 200, 200]
