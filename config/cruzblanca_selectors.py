"""
Selectores y configuración para Cruz Blanca Extranet
Identificados mediante exploración manual del sitio.

Fuente: https://extranet.cruzblanca.cl/login.aspx
"""

# ============================================================================
# PÁGINA DE LOGIN
# ============================================================================

LOGIN_URL = "https://extranet.cruzblanca.cl/login.aspx"

LOGIN_SELECTORS = {
    "username_input": "#LogAcceso_UserName",
    "password_input": "#LogAcceso_Password",
    "submit_button": "#LogAcceso_LoginImageButton",
    "form": "#login_form",
    "viewstate": "#__VIEWSTATE",
    "eventvalidation": "#__EVENTVALIDATION",
    "viewstategenerator": "#__VIEWSTATEGENERATOR",
    "eventtarget": "#__EVENTTARGET",
    "eventargument": "#__EVENTARGUMENT",
    "error_message": ".error",
    "username_required": "#LogAcceso_UserNameRequired",
    "password_required": "#LogAcceso_PasswordRequired",
}

HAS_RECAPTCHA = True

# ============================================================================
# POST-LOGIN / DASHBOARD
# ============================================================================

DASHBOARD_URL = "https://extranet.cruzblanca.cl/Extranet.aspx"

DASHBOARD_SELECTORS = {
    "success_indicator": "#lbNombreCliente",
    "user_name": "#lbNombreCliente",
    "user_rut": "#lblRutCliente",
    "title": "#lblTitulo",
    "menu_administracion": "#xbMenu_DXI0_",
    "menu_prestadores": "#xbMenu_DXI1_",
    "menu_mis_datos": "#xbMenu_DXI2_",
}

PRESTADORES_SUBMENU = {
    "cuenta_medica_manual": "#xbMenu_DXI1i0_",
    "prestador_consulta": "#xbMenu_DXI1i1_",
    "rendiciones_web": "#xbMenu_DXI1i2_",
    "solicitud_cobro": "#xbMenu_DXI1i3_",
    "control_recepcion": "#xbMenu_DXI1i4_",
    "consulta_cuentas": "#xbMenu_DXI1i5_",
    "certificado_tributario": "#xbMenu_DXI1i6_",
}

# ============================================================================
# LISTADO DE DOCUMENTOS/PDFs
# ============================================================================

IFRAME_SELECTOR = "#frame"
IFRAME_URL_PATTERN = "prestadores.cruzblanca.cl/CuentaMedicaDirecta/CuentaMedica.aspx"

CONTROL_RECEPCION_SELECTORS = {
    "filter_prestador": "input[type='text']",
    "filter_year": "select",
    "filter_month": "select",
    "filter_button": "input[type='submit'], button, input[value*='Consultar']",
    "tabla_resumen": "table",
    "resumen_headers": "th",
    "resumen_rows": "tr",
    "cuentas_a_pago_header": "th:has-text('Cuentas A Pago')",
    "cuentas_a_pago_cells": "td",
    "tabla_detalle": "table",
    "detalle_headers": "th:has-text('Nro. Cuenta')",
    "detalle_rows": "tr",
    "col_nro_cuenta": "td:nth-child(1)",
    "col_origen": "td:nth-child(2)",
    "col_estado": "td:nth-child(5)",
    "col_rut_afiliado": "td:nth-child(6)",
    "col_beneficiario": "td:nth-child(7)",
    "col_diagnostico": "td:nth-child(8)",
    "col_fecha_pago": "td:nth-child(9)",
    "col_historial": "td:nth-child(10)",
    "col_reporte_pdf": "td:nth-child(11)",
    "col_imagenes": "td:nth-child(12)",
    "pdf_link_onclick": "a[onclick*='AbrirImagen_ReporteLiquidacion']",
    "pdf_icon": "img[alt*='Reporte Liquidación']",
    "historial_link": "a[onclick*='AbrirHistorial']",
    "historial_icon": "img[alt*='Reporte Liquidación']",
    "pagination_container": ".dxgvPagerBottomPanel",
    "pagination_info": ".dxp-summary",
    "next_page": "a:has-text('Siguiente'), a[title*='Next']",
    "prev_page": "a:has-text('Anterior'), a[title*='Prev']",
    "page_numbers": "a.dxp-num",
}

PDF_LIST_SELECTORS = CONTROL_RECEPCION_SELECTORS
