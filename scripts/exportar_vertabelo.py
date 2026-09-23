"""Exporta estructura para diagramas, sin registros ni credenciales."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.db import connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('carpeta', type=Path)
    args = parser.parse_args()
    args.carpeta.mkdir(parents=True, exist_ok=True)
    def rows(query, params=None):
        with connection.cursor() as c:
            c.execute(query, params)
            return c.fetchall()
    def quote(name):
        return '"' + name.replace('"', '""') + '"'
    tables = rows("SELECT c.oid,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname")
    ddl = [
        '-- Portal NC simplificado: tablas fisicas para Vertabelo, PostgreSQL.',
        '-- Solo estructura. No ejecutar en la base existente.',
        '-- Incluye columnas, nulabilidad, claves primarias, unicas y relaciones.',
        '-- Las identidades se representan como serial/bigserial para importar.',
        '-- El esquema original adjunto conserva checks, indices, identidades y la vista registro_general.',
        '',
    ]
    constraints = []
    ncols = nfks = 0
    for oid, name in tables:
        columnas = []
        for col, typ, nonnull, identity, default in rows("SELECT a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity,pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum", [oid]):
            if identity:
                typ = {'bigint': 'bigserial', 'integer': 'serial', 'smallint': 'smallserial'}[typ]
            columnas.append('    ' + quote(col) + ' ' + typ + (' DEFAULT ' + default if default and not identity else '') + (' NOT NULL' if nonnull else ''))
        ncols += len(columnas)
        ddl.append('CREATE TABLE ' + quote(name) + ' (\n' + ',\n'.join(columnas) + '\n);\n')
        for cname, ctype, definition in rows("SELECT conname,contype,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%s AND contype IN ('p','u','f') ORDER BY conname", [oid]):
            constraints.append((ctype, 'ALTER TABLE ' + quote(name) + ' ADD CONSTRAINT ' + quote(cname) + ' ' + definition + ';'))
            nfks += ctype == 'f'
    ddl.extend(s for typ, s in constraints if typ != 'f')
    ddl.append('')
    ddl.extend(s for typ, s in constraints if typ == 'f')
    (args.carpeta / 'portal_nc_simplificado_vertabelo.sql').write_text('\n'.join(ddl) + '\n')
    d = settings.DATABASES['default']
    env = os.environ.copy()
    env['PGPASSWORD'] = d['PASSWORD']
    subprocess.run(['/Library/PostgreSQL/18/bin/pg_dump', '--schema-only', '--no-owner', '--no-privileges', '-h', d['HOST'], '-p', str(d['PORT']), '-U', d['USER'], '-d', d['NAME'], '-f', str(args.carpeta / 'portal_nc_esquema_original.sql')], env=env, check=True)
    print(f'Exportadas {len(tables)} tablas, {ncols} columnas y {nfks} relaciones. Sin datos.')


if __name__ == '__main__':
    main()
