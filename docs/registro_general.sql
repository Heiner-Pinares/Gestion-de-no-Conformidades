-- El Registro general ya no es una vista SQL.
-- La tabla física contiene el expediente base y el backend genera la proyección
-- de 34 columnas en apps/hallazgos/registro.py.
SELECT * FROM public.registro_general ORDER BY id;
