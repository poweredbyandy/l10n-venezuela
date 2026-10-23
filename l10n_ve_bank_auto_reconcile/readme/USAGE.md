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

El cron **Conciliación bancaria: procesar cola** toma la tanda siguiente.
También puede ejecutarlo a mano desde las acciones planificadas.
