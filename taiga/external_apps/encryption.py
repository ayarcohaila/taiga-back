# Copyright (C) 2014-2015 Andrey Antukh <niwi@niwi.be>
# Copyright (C) 2014-2015 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014-2015 David Barragán <bameda@dbarragan.com>
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

from Crypto.PublicKey import RSA
from jwkest.jwk import SYMKey
from jwkest.jwe import JWE


def encrypt(content, key):
    sym_key = SYMKey(key=key, alg="A128KW")
    jwe = JWE(content, alg="A128KW", enc="A256GCM")
    return jwe.encrypt([sym_key])


def decrypt(content, key):
    sym_key = SYMKey(key=key, alg="A128KW")
    return JWE().decrypt(content, keys=[sym_key])
