# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import re

from psycopg2 import sql

_logger = logging.getLogger(__name__)

TABLE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
AUDIT_LOG_TABLE = "l10n_ve_db_audit_log"
TRIGGER_FUNCTION = "l10n_ve_db_audit_trigger_func"

AUDIT_TRIGGER_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION l10n_ve_db_audit_trigger_func()
RETURNS trigger AS $$
DECLARE
    v_record_id integer;
    v_app_name text;
    v_old jsonb;
    v_new jsonb;
    v_changed jsonb;
    v_key text;
BEGIN
    v_app_name := COALESCE(current_setting('application_name', true), '');
    IF v_app_name LIKE 'odoo-%' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        v_record_id := OLD.id;
        v_old := row_to_json(OLD)::jsonb;
        v_changed := '{}'::jsonb;
        FOR v_key IN SELECT jsonb_object_keys(v_old)
        LOOP
            v_changed := v_changed || jsonb_build_object(
                v_key,
                jsonb_build_object('old', v_old -> v_key, 'new', NULL)
            );
        END LOOP;
        INSERT INTO l10n_ve_db_audit_log (
            table_name,
            record_id,
            operation,
            old_values,
            new_values,
            changed_values,
            db_user,
            client_addr,
            application_name,
            logged_at
        ) VALUES (
            TG_TABLE_NAME,
            v_record_id,
            'delete',
            v_old,
            NULL,
            v_changed,
            session_user,
            COALESCE(inet_client_addr()::text, ''),
            v_app_name,
            (NOW() AT TIME ZONE 'UTC')
        );
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        v_record_id := NEW.id;
        v_old := row_to_json(OLD)::jsonb;
        v_new := row_to_json(NEW)::jsonb;
        v_changed := '{}'::jsonb;
        FOR v_key IN SELECT jsonb_object_keys(v_new)
        LOOP
            IF v_old -> v_key IS DISTINCT FROM v_new -> v_key THEN
                v_changed := v_changed || jsonb_build_object(
                    v_key,
                    jsonb_build_object('old', v_old -> v_key, 'new', v_new -> v_key)
                );
            END IF;
        END LOOP;
        IF v_changed = '{}'::jsonb THEN
            RETURN NEW;
        END IF;
        INSERT INTO l10n_ve_db_audit_log (
            table_name,
            record_id,
            operation,
            old_values,
            new_values,
            changed_values,
            db_user,
            client_addr,
            application_name,
            logged_at
        ) VALUES (
            TG_TABLE_NAME,
            v_record_id,
            'update',
            v_old,
            v_new,
            v_changed,
            session_user,
            COALESCE(inet_client_addr()::text, ''),
            v_app_name,
            (NOW() AT TIME ZONE 'UTC')
        );
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        v_record_id := NEW.id;
        v_new := row_to_json(NEW)::jsonb;
        v_changed := '{}'::jsonb;
        FOR v_key IN SELECT jsonb_object_keys(v_new)
        LOOP
            v_changed := v_changed || jsonb_build_object(
                v_key,
                jsonb_build_object('old', NULL, 'new', v_new -> v_key)
            );
        END LOOP;
        INSERT INTO l10n_ve_db_audit_log (
            table_name,
            record_id,
            operation,
            old_values,
            new_values,
            changed_values,
            db_user,
            client_addr,
            application_name,
            logged_at
        ) VALUES (
            TG_TABLE_NAME,
            v_record_id,
            'insert',
            NULL,
            v_new,
            v_changed,
            session_user,
            COALESCE(inet_client_addr()::text, ''),
            v_app_name,
            (NOW() AT TIME ZONE 'UTC')
        );
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


def _validate_table_name(table_name):
    if not table_name or not TABLE_NAME_RE.match(table_name):
        raise ValueError("Invalid PostgreSQL table name: %s" % table_name)


def _table_exists(cr, table_name):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
        """,
        (table_name,),
    )
    return cr.fetchone()[0]


def _install_trigger_on_table(cr, table_name):
    _validate_table_name(table_name)
    if table_name == AUDIT_LOG_TABLE:
        return False
    if not _table_exists(cr, table_name):
        _logger.warning(
            "Skipping DB audit trigger: table %s does not exist", table_name
        )
        return False
    trigger_name = "l10n_ve_db_audit_%s" % table_name
    cr.execute(
        sql.SQL(
            """
            DROP TRIGGER IF EXISTS {trigger} ON {table};
            CREATE TRIGGER {trigger}
                AFTER INSERT OR UPDATE OR DELETE
                ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION {function}();
            """
        ).format(
            trigger=sql.Identifier(trigger_name),
            table=sql.Identifier(table_name),
            function=sql.Identifier(TRIGGER_FUNCTION),
        )
    )
    return True


def _drop_trigger_on_table(cr, table_name):
    _validate_table_name(table_name)
    if not _table_exists(cr, table_name):
        return
    trigger_name = "l10n_ve_db_audit_%s" % table_name
    cr.execute(
        sql.SQL("DROP TRIGGER IF EXISTS {trigger} ON {table}").format(
            trigger=sql.Identifier(trigger_name),
            table=sql.Identifier(table_name),
        )
    )


def install_db_audit_triggers(env, table_names=None):
    cr = env.cr
    cr.execute(AUDIT_TRIGGER_FUNCTION_SQL)
    if table_names is None:
        table_names = env["l10n.ve.db.audit.table"].search(
            [("active", "=", True)]
        ).mapped("table_name")
    installed = []
    for table_name in table_names:
        if _install_trigger_on_table(cr, table_name):
            installed.append(table_name)
    if installed:
        env["l10n.ve.db.audit.table"].sudo().search(
            [("table_name", "in", installed)]
        ).write({"trigger_installed": True})
    return installed


def uninstall_db_audit_triggers(env):
    cr = env.cr
    table_names = env["l10n.ve.db.audit.table"].search([]).mapped("table_name")
    for table_name in table_names:
        _drop_trigger_on_table(cr, table_name)
    cr.execute(
        sql.SQL("DROP FUNCTION IF EXISTS {function}()").format(
            function=sql.Identifier(TRIGGER_FUNCTION)
        )
    )
    env["l10n.ve.db.audit.table"].sudo().search([]).write(
        {"trigger_installed": False}
    )


def post_init_hook(env):
    install_db_audit_triggers(env)


def uninstall_hook(env):
    uninstall_db_audit_triggers(env)
