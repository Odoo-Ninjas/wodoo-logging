import os
import psycopg2
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError


class LogTable(models.Model):
    _name = "logging.data"

    date = fields.Datetime()
    level = fields.Selection(
        [
            ("INFO", "INFO"),
            ("ERROR", "ERROR"),
            ("WARN", "WARN"),
            ("DEBUG", "DEBUG"),
        ]
    )
    line = fields.Char()

    @api.model
    def _fetch_logs(self):
        conn = self._get_conn()
        cr = conn.cursor()
        try:

            cr.execute(
                """
                select id, date, ttime, line, level from console_log where 
                coalesce(exported, false) = false order by id desc
                limit 20000
                """
            )

            for rec in cr.fetchall():
                id, date, ttime, line, level = rec

                cr.execute(
                    """update console_log
                    set exported=true
                    where id = %s
                    """,
                    (id,),
                )

        finally:
            conn.close()

    @api.model
    def _get_conn(self):
        psycopg2.connect(
            host="fluentd_postgres",
            username="fluentd",
            password="fluentd",
            dbname="fluentd",
        )
