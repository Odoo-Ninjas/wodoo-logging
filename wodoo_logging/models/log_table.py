import os
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
    level = fields.Selection(
        [
            ("INFO", "INFO"),
            ("ERROR", "ERROR"),
            ("WARN", "WARN"),
            ("DEBUG", "DEBUG"),
        ]
    )
    line = fields.Text()
    _sql_constraints = [
        ('extid_unique', "unique(extid)", _("Only one unique entry allowed.")),
        
    ]

    @api.model
    def _fetch_logs(self):
        with self._get_conn() as (conn, cr):
            cr.execute(
                """
                select id, date, ttime, line, loglevel from console_log where 
                coalesce(exported, false) = false 
                order by id desc
                limit 20000
                """
            )

            for rec in cr.fetchall():
                id, date, ttime, line, level = rec
                if ttime:
                    ttime = ttime.split(",")[0]

                if level not in [x[0] for x in self._fields['level'].selection]:
                    level = False

                cr.execute(
                    """delete from console_log
                    where id = %s
                    """,
                    (id,),
                )
                if not self.search_count([('extid', '=', id)]):
                    strdate = f"{date} {ttime}" if date and ttime else False,
                    try:
                        if strdate:
                            datetime.datetime.strptime(strdate, DEFAULT_SERVER_DATETIME_FORMAT)
                    except:
                        strdate = False
                    self.create(
                        {
                            "extid": id,
                            "level": level or False,
                            "date": strdate,
                            "line": line,
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
            except: pass
            try:
                conn.close()
            except:
                pass
