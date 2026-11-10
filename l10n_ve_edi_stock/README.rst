=============================
Venezuela EDI Dispatch Guides
=============================

Base flow for sending Venezuelan dispatch guides through digital
invoicing. It validates the guide, builds the payload and records the
provider response on the outgoing picking.

Install the provider connector for the sales journal, for example
``l10n_ve_edi_stock_tfhka``, to send the guide.

**Table of contents**

.. contents::
   :local:

Use Cases / Context
===================

Customer invoices and withholding vouchers do not need inventory.
Dispatch guides do: they use the SENIAT control number, the dispatch
guide report and the delivery data from ``l10n_ve_stock``.

This module keeps that flow out of ``l10n_ve_edi``, so a company that
only emits invoices can install digital invoicing without stock.

Usage
=====

1. Install ``l10n_ve_edi_stock``. It is installed automatically when
   ``l10n_ve_edi`` and ``l10n_ve_stock`` are both installed.
2. Enable dispatch guides on the Venezuelan company and install the EDI
   connector of the sales journal.
3. Validate an outgoing picking that still needs a control number
   because the delivery is not fully invoiced.
4. Send the guide from the EDI tab on the picking.
5. Printing the local dispatch guide stays blocked until the EDI state
   is sent.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/OCA/l10n-venezuela/issues>`_.
In case of trouble, please check there if your issue has already been
reported. If you spotted it first, help us smash it by providing a
detailed and welcomed `feedback
<https://github.com/OCA/l10n-venezuela/issues/new?body=module:%20l10n_ve_edi_stock%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical
issues.

Credits
=======

Authors
-------

* andyengit

Contributors
------------

* andyengit

Maintainers
-----------

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

.. |maintainer-andyengit| image:: https://github.com/andyengit.png?size=40px
   :target: https://github.com/andyengit
   :alt: andyengit

Current `maintainer <https://odoo-community.org/page/maintainer-role>`__:

|maintainer-andyengit|

This module is part of the `OCA/l10n-venezuela
<https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_edi_stock>`_
project on GitHub.

You are welcome to contribute. To learn how please visit
https://odoo-community.org/page/Contribute.
