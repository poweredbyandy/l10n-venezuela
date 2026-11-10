===================================
Venezuela TFHKA EDI Dispatch Guides
===================================

The Factory HKA connector for Venezuelan dispatch guides. It sends the
guide, links it with the customer invoice (``facturaGuia``) and serves
the official TFHKA PDF on the picking and on the customer portal.

**Table of contents**

.. contents::
   :local:

Use Cases / Context
===================

``l10n_ve_edi_tfhka`` sends invoices, credit notes, debit notes and
withholding vouchers. Dispatch guides need stock data (origin,
destination, carrier, vehicle and the SENIAT guide), so that mapping
lives here and the invoice connector does not depend on inventory.

Usage
=====

1. Install ``l10n_ve_edi_stock_tfhka``. It is installed automatically
   when ``l10n_ve_edi_stock`` and ``l10n_ve_edi_tfhka`` are both
   installed.
2. Validate an outgoing picking that requires a SENIAT dispatch guide
   on a TFHKA sales journal.
3. Send the guide from the EDI tab.
4. Print stays blocked until the EDI state is sent. The portal can show
   the official TFHKA PDF.
5. When the related customer invoice is sent, the guide payload is
   updated with that invoice.

Guides for a contact whose country is not Venezuela send the foreign
identification type set on the contact and the tax ID without the
country prefix. Sending is blocked until both are set.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/OCA/l10n-venezuela/issues>`_.
In case of trouble, please check there if your issue has already been
reported. If you spotted it first, help us smash it by providing a
detailed and welcomed `feedback
<https://github.com/OCA/l10n-venezuela/issues/new?body=module:%20l10n_ve_edi_stock_tfhka%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

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
<https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_edi_stock_tfhka>`_
project on GitHub.

You are welcome to contribute. To learn how please visit
https://odoo-community.org/page/Contribute.
