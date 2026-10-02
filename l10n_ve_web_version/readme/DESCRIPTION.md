Muestra la versión de Odoo en la página de inicio de sesión y como
marca de agua en la esquina inferior derecha del backend.

El texto tiene la forma `Odoo Community v18.0` u `Odoo Enterprise v18.0`.
La versión sale del release del servidor (`odoo.release.version`) y la
edición depende de si `web_enterprise` está instalado.

La misma etiqueta se publica en `session_info` como `l10n_ve_version`,
para que otros módulos (por ejemplo el Punto de Venta) la muestren.
