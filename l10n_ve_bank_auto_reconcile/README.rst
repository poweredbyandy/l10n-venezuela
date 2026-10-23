=============================
Venezuela Bank Auto Reconcile
=============================

.. |badge1| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge2| image:: https://img.shields.io/badge/github-OCA%2Fl10n--venezuela-lightgray.png?logo=github
    :target: https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_bank_auto_reconcile
    :alt: OCA/l10n-venezuela

|badge1| |badge2|

Concilia extractos bancarios por referencia en una cola del módulo.

El botón guarda las líneas pendientes. El cron del módulo procesa 100
líneas o 30 segundos y, si quedan líneas, programa la tanda siguiente.
Si la cola está vacía, no concilia nada.

**Table of contents**

.. contents::
   :local:

Configuration
=============

El cron **Conciliación bancaria: procesar cola** queda activo y solo
procesa líneas que el botón puso en cola. El cron estándar de
conciliación bancaria permanece apagado.

Usage
=====

1. Abra la conciliación del banco.
2. Pulse **Conciliar automáticamente**. Las líneas pendientes quedan en
   la cola del módulo.
3. Pulse **Ver cola**, o vaya a **Contabilidad → Contabilidad →
   Cola de conciliación bancaria**, para ver las líneas que siguen
   pendientes.
4. En la conciliación del banco, el filtro **En cola** deja solo esas
   líneas.
5. Si la cola ya tiene esas líneas, un nuevo clic ejecuta una tanda del
   cron y encola solo líneas nuevas que aún no estén en cola.

El cron toma la tanda siguiente. También puede ejecutarlo a mano desde
las acciones planificadas.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/l10n-venezuela/issues>`_.
In case of trouble, please check there if your issue has already been reported.

Credits
=======

Authors
~~~~~~~

* andyengit

Contributors
~~~~~~~~~~~~

* Anderson Armeya <anderson.armeya@gmail.com>

Maintainers
~~~~~~~~~~~

This module is maintained by andyengit.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

This module is part of the `OCA/l10n-venezuela <https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_bank_auto_reconcile>`_ project on GitHub.
