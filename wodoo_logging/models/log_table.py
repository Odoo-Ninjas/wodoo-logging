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
    _order = "date desc"
    _log_access = False

    orig_line = fields.Char("Orig Line")
    extid = fields.Integer(index=True)
    tag = fields.Char("Container")
    date = fields.Datetime()
    method = fields.Char("Method")
    url = fields.Char("URL")
    is_traceback = fields.Boolean()
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
    def _parse(self):
        line = self.orig_line or ''
        if not line:
            return
        for level in [x[0] for x in self._fields["level"].selection]:
            if f" {level.upper()}" in line:
                line = line.replace(level, "")
                break
        else:
            level = False

        match = re.findall(r"\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d", line)
        if match:
            date = match[0]
            line = line.replace(match[0], "")
        else:
            date = False

        for method in ["GET", "POST"]:
            if f"{method} " in line:
                line = line.replace(method, "")
                break
        else:
            method = False

        match = re.findall(r"\ (\/[^\ ]*)", line)
        if match:
            url = match[0]
            line = line.replace(url, "")
        else:
            url = False

        line = self._make_nice_line(line)


        vals = {
            "level": level or False,
            "date": date or fields.Datetime.now(),
            "line": line,
            "method": method,
            "url": url,
        }
        vals['is_traceback'] = "Traceback" in line
        self.write(vals)

    @api.model
    def _make_nice_line(self, line):
        line = line.strip()
        if line.startswith(","):
            line = line.lstrip(",")
        line = line.split("?")
        if len(line) > 1:
            if len(line[0]) < 10:
                line = line[1]
        else:
            line = line[0]

        # 349 102 dbname longpolling
        if self.env.cr.dbname in line:
            line = line.split(self.env.cr.dbname)
            for c in "0123456789":
                line[0] = line[0].replace(c, "")
            line = self.env.cr.dbname.join(line).strip()
        return line



    @api.model
    def _fetch_logs(self):
        with self._get_conn() as (conn, cr):
            cr.execute(
                """
                select id, line, tag, col_datetime from console_log 
                order by id desc
                """
            )

            for rec in cr.fetchall():
                id, line, tag, date = rec
                orig_line = line
                if not date:
                    date = date or fields.Datetime.now()

                if not self.search_count([("extid", "=", id)]):
                    line = self.create(
                        {
                            "extid": id,
                            "orig_line": orig_line,
                            "date": date or fields.Datetime.now(),
                            "tag": tag,
                        }
                    )
                    self.flush()
                    line._parse()
                cr.execute(
                    """delete from console_log
                    where id = %s
                    """,
                    (id,),
                )
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
