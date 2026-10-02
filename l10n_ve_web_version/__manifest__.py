# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - Web Version",
    "summary": "Show the Odoo release on the login page and backend",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "version": "18.0.1.0.0",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Extra Tools",
    "depends": ["web"],
    "data": [
        "views/login_version.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_web_version/static/src/js/version_watermark.esm.js",
            "l10n_ve_web_version/static/src/xml/version_watermark.xml",
            "l10n_ve_web_version/static/src/scss/version_watermark.scss",
        ],
    },
    "license": "AGPL-3",
    "installable": True,
}
