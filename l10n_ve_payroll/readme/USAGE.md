1. Set the company currency to VES and fill Venezuela Payroll rates in Settings
   (rates are per company; VE structures and salary rules are shared /
   `company_id` empty so every company can use them).
2. On the employee/contract, choose a LOTTT working-time calendar installed by
   this module (Settings → Employees → Working Times, or contract Working Hours):

   - **VE LOTTT - Jornada diurna (40 h/sem)**: Mon–Fri 08:00–12:00 / 13:00–17:00
   - **VE LOTTT - Jornada mixta (37,5 h/sem)**: Mon–Fri 7.5 h/day
   - **VE LOTTT - Jornada nocturna (35 h/sem)**: Mon–Fri 00:00–07:00 (7 h/day)

   On each working-time calendar, open the tab **Non-working paid days** and
   list weekdays that are not worked but still count for salary (day + payslip
   code). VE calendars ship with Saturday=`DDESS` and Sunday=`DDESD`.
   Payslip create/refresh adds those Worked Days lines automatically.
3. Assign an employee a contract with a VE structure (e.g. Quincenal / Bi-weekly)
   and the wage in the contract currency (VES, USD or EUR).
4. Create a payslip for the period; the exchange rate is filled when the contract
   currency differs from the company currency.
5. Compute the sheet to generate assignment, deduction and employer contribution
   lines (SSO, FAOV, RPE, INCES, ISLR, loans, etc.).
6. Confirm the payslip. Structures marked to process social benefits can accrue
   prestaciones on done.
