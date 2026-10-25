Install after `l10n_ve_payroll` and `l10n_ve_seniat`.

On install/upgrade (and when loading a SENIAT chart of accounts), the module:

1. Ensures payroll liability/expense accounts exist (SENIAT codes such as
   `2103020`, `5102001`, `2103003`…) and receivable `1106002` Prestamos a
   empleados.
2. Maps salary rule debit/credit accounts from those codes (CRED / INTCRED
   credit `1106002`).
3. Sets **Settings → Payroll → Loan receivable account** on the company
   (default `1106002`). Disbursement uses that account; it is not chosen
   per loan.

- Chart `ve_seniat`: uses accounts from the official CoA CSV.
- Charts `ve_seniat_basic` / `ve_seniat_empty`: creates the same payroll
  accounts via `account.chart.template` and maps the rules.

## Confirm payslip (accrual)

Confirm a payslip to generate the journal entry (expenses / withholdings vs
`2103020` Nómina por pagar).

## Register payment (cash out)

1. Open a confirmed payslip (or a batch / select several payslips).
2. Click **Register Payment**.
3. Choose the **bank or cash journal** (where the money left), payment date
   and amounts (partial payments allowed). The default amount is the
   **2103020 balance from the payslip journal entry** (not salary rule
   `TOTAL`), so multicurrency rounding of Bs 0.01 does not leave the payable
   open.
4. Confirm: creates a posted entry `Dr 2103020 / Cr bank-cash` and marks the
   payslip as paid when the residual is zero.

Social security liabilities (`210300x`) are paid separately to each agency.
