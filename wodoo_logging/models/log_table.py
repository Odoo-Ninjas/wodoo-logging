import os
import re
import datetime
import psycopg2
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import contextlib
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class LogTable(models.Model):
    _name = "logging.data"
    _order = "extid desc"
    _log_access = False

    extid = fields.Integer(index=True)
    tag = fields.Char("Container")
    date = fields.Datetime()
    method = fields.Char("Method")
    url = fields.Char("URL")
    level = fields.Selection(
        [
            ("INFO", "INFO"),
            ("ERROR", "ERROR"),
            ("WARN", "WARN"),
            ("DEBUG", "DEBUG"),
            ("CRITICAL", "CRITICAL"),
        ]
    )
    line = fields.Text()
    _sql_constraints = [
        ("extid_unique", "unique(extid)", _("Only one unique entry allowed.")),
    ]

    @api.model
    def _parse_line(self, line):
        for level in [x[0] for x in self._fields["level"].selection]:
            if f" {level.upper()}" in line:
                break
        else:
            level = False

        match = re.findall(r"\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d", line)
        if match:
            date = match[0]
        else:
            date = False

        for method in ["GET", "POST"]:
            if f" {method} " in line:
                break
        else:
            method = False

        match = re.findall(r"/\ \/[^\ ]*", line)
        if match:
            url = match[0]
        else:
            url = False

        return date, level, method, url

    @api.model
    def _fetch_logs(self):
        with self._get_conn() as (conn, cr):
            cr.execute(
                """
                select id, line, tag from console_log where 
                coalesce(exported, false) = false 
                order by id desc
                limit 20000
                """
            )

            for rec in cr.fetchall():
                id, line, tag = rec
                date, level, method, url = self._parse_line(line)

                cr.execute(
                    """delete from console_log
                    where id = %s
                    """,
                    (id,),
                )
                if not self.search_count([("extid", "=", id)]):
                    self.create(
                        {
                            "extid": id,
                            "level": level or False,
                            "date": date,
                            "line": line,
                            "tag": tag,
                            "method": method,
                            "url": url,
                        }
                    )
                    self.flush()
                self.env.cr.commit()
                conn.commit()

    @contextlib.contextmanager
    @api.model
    def _get_conn(self):
        conn = psycopg2.connect(
            host="fluentd_postgres",
            user="fluentd",
            password="fluentd",
            dbname="fluentd",
        )
        try:
            cr = conn.cursor()
            yield conn, cr
            conn.commit()
        finally:
            try:
                cr.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass
