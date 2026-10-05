from django.db import migrations

SQL = r"""
DO $$ DECLARE r record; BEGIN
  FOR r IN
    SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
    WHERE n.nspname='public' AND left(t.typname, 5) = '_aux_'
  LOOP
    EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(r.typname) || ' CASCADE';
  END LOOP;
END $$;
"""

class Migration(migrations.Migration):
    dependencies = [("hallazgos", "0014_ajustar_relaciones_compartidas")]
    operations = [migrations.RunSQL(SQL, migrations.RunSQL.noop)]
