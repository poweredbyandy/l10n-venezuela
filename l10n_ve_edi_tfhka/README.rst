=======================
Venezuela TFHKA EDI
=======================

Connector for The Factory HKA digital invoicing in Venezuela. It sends
customer invoices, credit and debit notes, dispatch guides and
withholding vouchers through the TFHKA API, stores the provider
response and serves the official digital PDF. It also queries the
numbering ranges available in TFHKA and assigns a new range when none
is available.

The payload follows the TFHKA API technical reference v2.2
(``static/description/tfhka_api_reference.pdf``), including IGTF debit
notes (transaction type 98) and buyers not domiciled in Venezuela.

**Table of contents**

.. contents::
   :local:

Use Cases / Context
===================

Companies that already use ``l10n_ve_edi`` and emit documents through
The Factory HKA need a provider-specific connector: authentication,
payload mapping, numbering range management, official PDF download and
portal display of the digital document.

Configuration
=============

1. Install ``l10n_ve_edi_tfhka`` after ``l10n_ve_edi``.
2. In **Settings**, set the TFHKA environment, API URL, username and
   password. Test the connection before emitting live documents.
3. On each sales or withholding journal used for digital emission,
   choose provider **The Factory HKA** and set serie, branch and
   environment digit so they match the numbering range in the TFHKA
   portal.
4. Click **Numeración TFHKA** on the journal to check that TFHKA has an
   available numbering range for each document type you emit.
5. For customers outside Venezuela, set the country, the tax ID and the
   field **Tipo de identificación extranjera (TFHKA)** (for example RUT
   or NIT) on the contact.

Usage
=====

Numbering ranges
----------------

1. Open a journal with provider **The Factory HKA** and click
   **Numeración TFHKA**. Only accounting administrators see the button.
2. Choose the document type. The serie comes from the journal and the
   proposed ``numeroDocumento`` range covers the selected month with the
   same format Odoo uses when emitting.
3. Click **Consultar** to see whether TFHKA has an available range.
4. Click **Consultar y asignar si no existe** to assign the range shown
   when TFHKA has none available. Nothing is assigned if a range
   already exists.

TFHKA rejects the assignment when the taxpayer has no control numbers
loaded. In that case ask The Factory HKA or your distributor to load a
batch of control numbers and assign the range again.

Customer invoices
-----------------

1. Confirm a customer invoice or credit note on a TFHKA journal.
2. Send the document from the EDI tab, or retry if the send failed.
3. When the state is sent, print or open the official TFHKA PDF.

IGTF debit notes
----------------

1. Create a debit note from the invoice whose IGTF must be adjusted.
2. Book every line of the debit note on the company IGTF account, with
   the exempt sales tax.
3. Send it from the EDI tab. It is sent with transaction type 98 and
   the IGTF taxable base in USD and in bolivars.

Customers outside Venezuela
---------------------------

Invoices and dispatch guides for a contact whose country is not
Venezuela send the foreign identification type set on the contact and
the tax ID without the country prefix. Sending is blocked until both
are set.

Dispatch guides
---------------

1. Validate an outgoing picking that requires a SENIAT dispatch guide
   on a TFHKA sales journal.
2. Send the guide from the EDI tab.
3. Print is blocked until the EDI state is sent. The portal can show
   the official TFHKA PDF.

Withholding vouchers
--------------------

1. Emit an IVA or ISLR supplier withholding.
2. Send it from the EDI tab after the voucher has a number.
3. Print uses the official TFHKA PDF when the voucher was sent.

Known issues / Roadmap
======================

- Other taxes (OTI, ``otrosImpuestosSubtotal`` with ``codigoOTI``,
  ``porcentajeOTI``, ``baseImponibleOTI`` and ``montoOTI``) are not sent.
  ``l10n_ve_seniat`` allows a single tax per invoice line, so a municipal
  tax cannot be recorded on top of VAT.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/OCA/l10n-venezuela/issues>`_.
In case of trouble, please check there if your issue has already been
reported. If you spotted it first, help us smash it by providing a
detailed and welcomed `feedback
<https://github.com/OCA/l10n-venezuela/issues/new?body=module:%20l10n_ve_edi_tfhka%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

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

This module is part of the `OCA/l10n-venezuela
<https://github.com/OCA/l10n-venezuela/tree/18.0/l10n_ve_edi_tfhka>`_
project on GitHub.

You are welcome to contribute. To learn how please visit
https://odoo-community.org/page/Contribute.
