# -*- coding: utf-8 -*-
# Copyright (C) 2014-2017 Andrey Antukh <niwi@niwi.nz>
# Copyright (C) 2014-2017 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014-2017 David Barragán <bameda@dbarragan.com>
# Copyright (C) 2014-2017 Alejandro Alonso <alejandro.alonso@kaleidos.net>
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

import logging
import sys

from django.utils.translation import ugettext as _

from taiga.base.mails import mail_builder
from taiga.celery import app
from taiga.users.models import User
from .importer import GithubImporter

logger = logging.getLogger('taiga.importers.github')


@app.task(bind=True)
def import_project(self, user_id, token, project_id, options):
    user = User.object.get(id=user_id)
    importer = GithubImporter(user, token)
    try:
        project = importer.import_project(project_id, options)
    except Exception as e:
        # Error
        ctx = {
            "user": user,
            "error_subject": _("Error importing GitHub project"),
            "error_message": _("Error importing GitHub project"),
            "project": project_id,
            "exception": e
        }
        email = mail_builder.github_import_error(admin, ctx)
        email.send()
        logger.error('Error importing GitHub project %s (by %s)', project_id, user, exc_info=sys.exc_info())
    else:
        ctx = {
            "project": project,
            "user": user,
        }
        email = mail_builder.github_import_success(user, ctx)
        email.send()
