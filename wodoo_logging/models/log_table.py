from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class LogTable(models.Model):
    _name = "logging.data"

    date = fields.Datetime()
    level = fields.Selection([
        ('INFO', 'INFO'),
        ('ERROR', 'ERROR'),
        ('WARN', 'WARN'),
        ('DEBUG', 'DEBUG'),
    ])
    line = fields.Char()
