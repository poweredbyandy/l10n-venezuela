#!/usr/bin/env python3
import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import polib
from deep_translator import GoogleTranslator

REPO_ROOT = Path(__file__).resolve().parent

PH_PATTERN = re.compile(
    r"%\([a-zA-Z_][a-zA-Z0-9_]*\)[a-zA-ZdiouxXeEfFgGcrs%]"
    r"|\{[a-zA-Z_][a-zA-Z0-9_]*\}"
    r"|\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}"
)

ENGLISH_WORDS = re.compile(
    r"\b(the|and|for|with|from|this|that|your|specify|necessary|please|display|"
    r"custom|groupby|warning|exception|entry|item|items|chart|template|settings|"
    r"config|type|icon|activity|next|name|reconciled|specify|necessary|cierre|"
    r"closing|revise|publicar|published|expected|errors|lines|options|report|"
    r"expression|formula|subformula|token|child|parent|label|line|book|section|"
    r"country|company|code|already|this|currency|partner|amount|payment|journal|"
    r"invoice|invoices|warehouse|price|discount|picking|order|move|account)\b",
    re.IGNORECASE,
)

MANUAL_FIXES = {
    "Exception Type": "Tipo de excepción",
    "Display Custom Groupby Warning": "Advertencia de agrupación personalizada",
    "Please specify the accounts necessary for the Tax Closing Entry.": (
        "Por favor especifique las cuentas necesarias para el asiento de cierre fiscal."
    ),
    "Activity Type Icon": "Icono del tipo de actividad",
    "Next Activity Type": "Siguiente tipo de actividad",
    "Display Name": "Nombre para mostrar",
    "L10N Ve Dispatch Display Currency": "Moneda de visualización del despacho",
    "Display Type": "Tipo de visualización",
    "Journal Entry": "Asiento contable",
    "Journal Item": "Apunte contable",
    "Journal Items": "Apuntes contables",
    "Account Chart Template": "Plantilla del plan de cuentas",
    "Config Settings": "Ajustes de configuración",
    "Journal": "Diario",
    "Journals": "Diarios",
    "Account": "Cuenta",
    "Accounts": "Cuentas",
    "Partner": "Contacto",
    "Partners": "Contactos",
    "Product": "Producto",
    "Products": "Productos",
    "Invoice": "Factura",
    "Invoices": "Facturas",
    "Payment": "Pago",
    "Payments": "Pagos",
    "Company": "Compañía",
    "Companies": "Compañías",
    "Currency": "Moneda",
    "Currencies": "Monedas",
    "Country": "País",
    "Countries": "Países",
    "State": "Estado",
    "States": "Estados",
    "User": "Usuario",
    "Users": "Usuarios",
    "Group": "Grupo",
    "Groups": "Grupos",
    "Report": "Reporte",
    "Reports": "Reportes",
    "Settings": "Ajustes",
    "Configuration": "Configuración",
    "Description": "Descripción",
    "Reference": "Referencia",
    "Amount": "Monto",
    "Date": "Fecha",
    "Number": "Número",
    "Code": "Código",
    "Name": "Nombre",
    "Type": "Tipo",
    "Status": "Estado",
    "Total": "Total",
    "Subtotal": "Subtotal",
    "Tax": "Impuesto",
    "Taxes": "Impuestos",
    "Line": "Línea",
    "Lines": "Líneas",
    "Order": "Orden",
    "Orders": "Órdenes",
    "Warehouse": "Almacén",
    "Warehouses": "Almacenes",
    "Customer": "Cliente",
    "Customers": "Clientes",
    "Vendor": "Proveedor",
    "Vendors": "Proveedores",
    "Supplier": "Proveedor",
    "Suppliers": "Proveedores",
    "Employee": "Empleado",
    "Employees": "Empleados",
    "Contact": "Contacto",
    "Contacts": "Contactos",
    "Address": "Dirección",
    "Phone": "Teléfono",
    "Email": "Correo electrónico",
    "Website": "Sitio web",
    "City": "Ciudad",
    "Street": "Calle",
    "Zip": "Código postal",
    "Bank": "Banco",
    "Banks": "Bancos",
    "Balance": "Saldo",
    "Debit": "Débito",
    "Credit": "Crédito",
    "Draft": "Borrador",
    "Posted": "Publicado",
    "Cancelled": "Cancelado",
    "Confirmed": "Confirmado",
    "Validated": "Validado",
    "Pending": "Pendiente",
    "Done": "Hecho",
    "Active": "Activo",
    "Inactive": "Inactivo",
    "Enabled": "Habilitado",
    "Disabled": "Deshabilitado",
    "Required": "Requerido",
    "Optional": "Opcional",
    "Default": "Predeterminado",
    "Custom": "Personalizado",
    "Manual": "Manual",
    "Automatic": "Automático",
    "Create": "Crear",
    "Edit": "Editar",
    "Delete": "Eliminar",
    "Save": "Guardar",
    "Cancel": "Cancelar",
    "Confirm": "Confirmar",
    "Validate": "Validar",
    "Print": "Imprimir",
    "Export": "Exportar",
    "Import": "Importar",
    "Download": "Descargar",
    "Upload": "Subir",
    "Search": "Buscar",
    "Filter": "Filtrar",
    "Show": "Mostrar",
    "Hide": "Ocultar",
    "Help": "Ayuda",
    "Warning": "Advertencia",
    "Error": "Error",
    "Success": "Éxito",
    "Message": "Mensaje",
    "Messages": "Mensajes",
    "Notification": "Notificación",
    "Notifications": "Notificaciones",
    "Attachment": "Adjunto",
    "Attachments": "Adjuntos",
    "File": "Archivo",
    "Files": "Archivos",
    "Image": "Imagen",
    "Images": "Imágenes",
    "Icon": "Icono",
    "Icons": "Iconos",
    "Label": "Etiqueta",
    "Labels": "Etiquetas",
    "Tag": "Etiqueta",
    "Tags": "Etiquetas",
    "Category": "Categoría",
    "Categories": "Categorías",
    "Sequence": "Secuencia",
    "Priority": "Prioridad",
    "Version": "Versión",
    "Module": "Módulo",
    "Modules": "Módulos",
    "Model": "Modelo",
    "Models": "Modelos",
    "Field": "Campo",
    "Fields": "Campos",
    "Record": "Registro",
    "Records": "Registros",
    "View": "Vista",
    "Views": "Vistas",
    "Form": "Formulario",
    "List": "Lista",
    "Tree": "Lista",
    "Kanban": "Kanban",
    "Graph": "Gráfico",
    "Pivot": "Tabla dinámica",
    "Calendar": "Calendario",
    "Activity": "Actividad",
    "Activities": "Actividades",
    "Menu": "Menú",
    "Action": "Acción",
    "Actions": "Acciones",
    "Rule": "Regla",
    "Rules": "Reglas",
    "Access": "Acceso",
    "Permission": "Permiso",
    "Permissions": "Permisos",
    "Security": "Seguridad",
    "Audit": "Auditoría",
    "Log": "Registro",
    "Logs": "Registros",
    "Queue": "Cola",
    "Job": "Trabajo",
    "Jobs": "Trabajos",
    "Session": "Sesión",
    "Sessions": "Sesiones",
    "Receipt": "Recibo",
    "Receipts": "Recibos",
    "Ticket": "Ticket",
    "Tickets": "Tickets",
    "Cash": "Efectivo",
    "Register": "Caja",
    "Opening": "Apertura",
    "Closing": "Cierre",
    "Shift": "Turno",
    "Shifts": "Turnos",
    "Batch": "Lote",
    "Batches": "Lotes",
    "Lot": "Lote",
    "Lots": "Lotes",
    "Serial": "Serial",
    "Barcode": "Código de barras",
    "Location": "Ubicación",
    "Locations": "Ubicaciones",
    "Zone": "Zona",
    "Zones": "Zonas",
    "Route": "Ruta",
    "Routes": "Rutas",
    "Operation": "Operación",
    "Operations": "Operaciones",
    "Transfer": "Transferencia",
    "Transfers": "Transferencias",
    "Delivery": "Entrega",
    "Dispatch": "Despacho",
    "Guide": "Guía",
    "Reason": "Motivo",
    "Source": "Origen",
    "Destination": "Destino",
    "Origin": "Origen",
    "Target": "Destino",
    "Input": "Entrada",
    "Output": "Salida",
    "Incoming": "Entrante",
    "Outgoing": "Saliente",
    "Internal": "Interno",
    "External": "Externo",
    "Return": "Devolución",
    "Returns": "Devoluciones",
    "Scrap": "Desecho",
    "Adjustment": "Ajuste",
    "Adjustments": "Ajustes",
    "Valuation": "Valoración",
    "Cost": "Costo",
    "Costs": "Costos",
    "Price": "Precio",
    "Prices": "Precios",
    "Discount": "Descuento",
    "Discounts": "Descuentos",
    "Margin": "Margen",
    "Margins": "Márgenes",
    "Profit": "Ganancia",
    "Loss": "Pérdida",
    "Income": "Ingreso",
    "Expense": "Gasto",
    "Expenses": "Gastos",
    "Revenue": "Ingreso",
    "Revenues": "Ingresos",
    "Asset": "Activo",
    "Assets": "Activos",
    "Liability": "Pasivo",
    "Liabilities": "Pasivos",
    "Equity": "Patrimonio",
    "Capital": "Capital",
    "Receivable": "Por cobrar",
    "Payable": "Por pagar",
    "Due": "Vencido",
    "Overdue": "Vencido",
    "Paid": "Pagado",
    "Unpaid": "No pagado",
    "Open": "Abierto",
    "Closed": "Cerrado",
    "Locked": "Bloqueado",
    "Unlocked": "Desbloqueado",
    "Archived": "Archivado",
    "Duplicate": "Duplicado",
    "Copy": "Copia",
    "Original": "Original",
    "Related": "Relacionado",
    "Linked": "Vinculado",
    "Assigned": "Asignado",
    "Available": "Disponible",
    "Unavailable": "No disponible",
    "Reserved": "Reservado",
    "Ready": "Listo",
    "Waiting": "En espera",
    "Backorder": "Pedido pendiente",
    "Backorders": "Pedidos pendientes",
    "Deadline": "Fecha límite",
    "Duration": "Duración",
    "Owner": "Propietario",
    "Responsible": "Responsable",
    "Child": "Hijo",
    "Parent": "Padre",
    "Children": "Hijos",
    "Parents": "Padres",
    "Main": "Principal",
    "Secondary": "Secundario",
    "Additional": "Adicional",
    "Extra": "Extra",
    "Other": "Otro",
    "Others": "Otros",
    "Unknown": "Desconocido",
    "Empty": "Vacío",
    "Blank": "En blanco",
    "Null": "Nulo",
    "Zero": "Cero",
    "First": "Primero",
    "Last": "Último",
    "Next": "Siguiente",
    "Previous": "Anterior",
    "Current": "Actual",
    "New": "Nuevo",
    "Old": "Antiguo",
    "Recent": "Reciente",
    "Latest": "Más reciente",
    "Minimum": "Mínimo",
    "Maximum": "Máximo",
    "Average": "Promedio",
    "Sum": "Suma",
    "Count": "Conteo",
    "Value": "Valor",
    "Values": "Valores",
    "Unit": "Unidad",
    "Units": "Unidades",
    "Measure": "Medida",
    "Weight": "Peso",
    "Volume": "Volumen",
    "Length": "Longitud",
    "Width": "Ancho",
    "Height": "Altura",
    "Size": "Tamaño",
    "Color": "Color",
    "Logo": "Logo",
    "Banner": "Banner",
    "Background": "Fondo",
    "Foreground": "Primer plano",
    "Style": "Estilo",
    "Styles": "Estilos",
    "Theme": "Tema",
    "Themes": "Temas",
    "Font": "Fuente",
    "Fonts": "Fuentes",
    "Language": "Idioma",
    "Languages": "Idiomas",
    "Translation": "Traducción",
    "Translations": "Traducciones",
    "Locale": "Configuración regional",
    "Timezone": "Zona horaria",
    "Format": "Formato",
    "Decimal": "Decimal",
    "Separator": "Separador",
    "Rounding": "Redondeo",
    "Precision": "Precisión",
    "Scale": "Escala",
    "Factor": "Factor",
    "Ratio": "Proporción",
    "Share": "Participación",
    "Part": "Parte",
    "Fraction": "Fracción",
    "Integer": "Entero",
    "Float": "Flotante",
    "Boolean": "Booleano",
    "String": "Cadena",
    "Text": "Texto",
    "Binary": "Binario",
    "Selection": "Selección",
    "Relation": "Relación",
    "Relations": "Relaciones",
    "Index": "Índice",
    "Indexes": "Índices",
    "Unique": "Único",
    "Clone": "Clon",
    "Backup": "Respaldo",
    "Restore": "Restaurar",
    "Recovery": "Recuperación",
    "Archive": "Archivar",
    "Trash": "Papelera",
    "Remove": "Eliminar",
    "Insert": "Insertar",
    "Append": "Anexar",
    "Replace": "Reemplazar",
    "Move": "Mover",
    "Sort": "Ordenar",
    "Ascending": "Ascendente",
    "Descending": "Descendente",
    "Limit": "Límite",
    "Offset": "Desplazamiento",
    "Pagination": "Paginación",
    "Template": "Plantilla",
    "Templates": "Plantillas",
    "Layout": "Diseño",
    "Header": "Encabezado",
    "Footer": "Pie de página",
    "Body": "Cuerpo",
    "Content": "Contenido",
    "Title": "Título",
    "Subtitle": "Subtítulo",
    "Table": "Tabla",
    "Column": "Columna",
    "Columns": "Columnas",
    "Row": "Fila",
    "Rows": "Filas",
    "Cell": "Celda",
    "Cells": "Celdas",
    "Sheet": "Hoja",
    "Page": "Página",
    "Pages": "Páginas",
    "Document": "Documento",
    "Documents": "Documentos",
    "Signature": "Firma",
    "Signatures": "Firmas",
    "Certificate": "Certificado",
    "Certificates": "Certificados",
    "License": "Licencia",
    "Licenses": "Licencias",
    "Registration": "Registro",
    "Registrations": "Registros",
    "Machine": "Máquina",
    "Machines": "Máquinas",
    "Device": "Dispositivo",
    "Devices": "Dispositivos",
    "Terminal": "Terminal",
    "Terminals": "Terminales",
    "Provider": "Proveedor",
    "Service": "Servicio",
    "Endpoint": "Punto de conexión",
    "Connection": "Conexión",
    "Connected": "Conectado",
    "Disconnected": "Desconectado",
    "Online": "En línea",
    "Offline": "Fuera de línea",
    "Sync": "Sincronizar",
    "Synchronized": "Sincronizado",
    "Process": "Procesar",
    "Processing": "Procesando",
    "Processed": "Procesado",
    "Generate": "Generar",
    "Generated": "Generado",
    "Calculate": "Calcular",
    "Calculated": "Calculado",
    "Computation": "Cálculo",
    "Formula": "Fórmula",
    "Expression": "Expresión",
    "Condition": "Condición",
    "Conditions": "Condiciones",
    "Constraint": "Restricción",
    "Constraints": "Restricciones",
    "Validation": "Validación",
    "Validations": "Validaciones",
    "Compliance": "Cumplimiento",
    "Regulation": "Regulación",
    "Regulations": "Regulaciones",
    "Law": "Ley",
    "Decree": "Decreto",
    "Article": "Artículo",
    "Paragraph": "Párrafo",
    "Section": "Sección",
    "Chapter": "Capítulo",
    "Annex": "Anexo",
    "Appendix": "Apéndice",
    "Withholding": "Retención",
    "Retention": "Retención",
    "Advance": "Anticipo",
    "Fiscal": "Fiscal",
    "Taxable": "Gravable",
    "Contributor": "Contribuyente",
    "Taxpayer": "Contribuyente",
    "Withholder": "Agente de retención",
    "Voucher": "Comprobante",
    "Book": "Libro",
    "Purchase": "Compra",
    "Sale": "Venta",
    "Sales": "Ventas",
    "Purchases": "Compras",
    "Stock": "Inventario",
    "Inventory": "Inventario",
    "Picking": "Albarán",
    "POS Order": "Orden TPV",
    "POS Orders": "Órdenes TPV",
    "POS Session": "Sesión TPV",
    "POS Sessions": "Sesiones TPV",
    "POS Payment": "Pago TPV",
    "POS Payments": "Pagos TPV",
    "POS Config": "Configuración TPV",
    "POS Category": "Categoría TPV",
    "POS Product": "Producto TPV",
    "POS Receipt": "Recibo TPV",
    "POS Invoice": "Factura TPV",
    "POS Invoices": "Facturas TPV",
}


def protect_placeholders(text):
    tokens = {}

    def replacer(match):
        token = f"__PH{len(tokens)}__"
        tokens[token] = match.group(0)
        return token

    protected = PH_PATTERN.sub(replacer, text)
    return protected, tokens


def restore_placeholders(text, tokens):
    for token, original in sorted(
        tokens.items(), key=lambda x: len(x[0]), reverse=True
    ):
        text = text.replace(token, original)
    return text


def get_placeholders(text):
    return PH_PATTERN.findall(text or "")


def fix_placeholder_names(msgid, msgstr):
    src = get_placeholders(msgid)
    dst = get_placeholders(msgstr)
    if not src:
        return msgstr
    if len(src) != len(dst):
        return None
    result = msgstr
    for source, target in zip(src, dst, strict=False):
        if source != target:
            result = result.replace(target, source, 1)
    return result


def has_english_remnants(text):
    if not text:
        return False
    return bool(ENGLISH_WORDS.search(text))


def translate_text(text, translator, cache):
    if text in MANUAL_FIXES:
        return MANUAL_FIXES[text]
    if text in cache:
        return cache[text]
    protected, tokens = protect_placeholders(text)
    try:
        translated = translator.translate(protected)
        time.sleep(0.05)
    except Exception as exc:
        print(f"  [WARN] {text[:60]!r}: {exc}")
        translated = text
    translated = restore_placeholders(translated, tokens)
    cache[text] = translated
    return translated


def needs_fix(entry):
    if entry.obsolete or not entry.msgid:
        return False
    msgstr = entry.msgstr or ""
    src_ph = get_placeholders(entry.msgid)
    dst_ph = get_placeholders(msgstr)
    if src_ph and src_ph != dst_ph:
        return True
    if entry.msgid in MANUAL_FIXES and msgstr != MANUAL_FIXES[entry.msgid]:
        return True
    if has_english_remnants(msgstr) and not has_english_remnants(entry.msgid):
        return True
    if entry.fuzzy:
        return True
    return False


def fix_entry(entry, translator, cache):
    msgid = entry.msgid
    msgstr = entry.msgstr or ""

    if msgid in MANUAL_FIXES:
        return MANUAL_FIXES[msgid]

    fixed_ph = fix_placeholder_names(msgid, msgstr)
    if fixed_ph is not None and get_placeholders(fixed_ph) == get_placeholders(msgid):
        if not has_english_remnants(fixed_ph) or has_english_remnants(msgid):
            return fixed_ph
        msgstr = fixed_ph

    if has_english_remnants(msgstr) and not has_english_remnants(msgid):
        return translate_text(msgid, translator, cache)

    if get_placeholders(msgid) and get_placeholders(msgid) != get_placeholders(msgstr):
        return translate_text(msgid, translator, cache)

    return fixed_ph if fixed_ph is not None else msgstr


def fix_po_file(po_path, translator, cache, dry_run=False):
    po = polib.pofile(str(po_path))
    module = po_path.parent.parent.name
    fixed = 0

    for entry in po:
        if not needs_fix(entry):
            continue
        new_msgstr = fix_entry(entry, translator, cache)
        if new_msgstr != (entry.msgstr or ""):
            entry.msgstr = new_msgstr
            entry.flags = [flag for flag in entry.flags if flag != "fuzzy"]
            fixed += 1

    if fixed and not dry_run:
        po.metadata["PO-Revision-Date"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M%z"
        )
        po.metadata["Language"] = "es_VE"
        po.save(str(po_path))

    return module, fixed


def parse_args():
    parser = argparse.ArgumentParser(
        description="Corrige placeholders y traducciones en es_VE.po."
    )
    parser.add_argument("-m", "--modules", nargs="*", help="Módulos específicos.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    po_files = sorted(REPO_ROOT.glob("*/i18n/es_VE.po"))
    if args.modules:
        po_files = [p for p in po_files if p.parent.parent.name in args.modules]

    translator = GoogleTranslator(source="en", target="es")
    cache = {}
    total = 0

    for po_path in po_files:
        module, fixed = fix_po_file(po_path, translator, cache, dry_run=args.dry_run)
        if fixed:
            action = "corregiría" if args.dry_run else "corrigió"
            print(f"[OK] {module}: {action} {fixed} entradas")
            total += fixed
        else:
            print(f"[SKIP] {module}: sin correcciones")

    print(
        f"\nTotal: {total} entradas {'a corregir' if args.dry_run else 'corregidas'}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
