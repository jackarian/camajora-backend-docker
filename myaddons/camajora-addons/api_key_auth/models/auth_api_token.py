# Copyright 2020 Metadonors srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import os

from binascii import hexlify
from odoo import api, fields, models, _

TOKEN_LENGHT = 32


class AuthApiToken(models.Model):

    _name = 'auth.api.token'
    _description = 'Auth Api Token'

    def _default_user_id(self):
        return self.env.user

    user_id = fields.Many2one(
        'res.users',
        string=_('User'),
        required=True,
        default=_default_user_id
    )

    token = fields.Char(string=_("API Key"), readonly=True)

    @api.model
    def retrieve_from_user(self, user_id):
        keys = self.search([
            ('user_id', '=', user_id.id)
        ])

        if len(keys) > 0:
            return keys[0]

        key = self.create({
            'user_id': user_id.id
        })

        return key

    @api.model
    def retrieve_from_api_key(self, api_key):
        keys = self.search([
            ('token', '=', api_key)
        ])

        if len(keys) > 0:
            return keys[0]

        return False

    def _generate_token(self):
        return hexlify(os.urandom(TOKEN_LENGHT))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['token'] = self._generate_token()
        return super().create(vals_list)
