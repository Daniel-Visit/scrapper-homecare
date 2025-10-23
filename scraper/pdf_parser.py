"""Parser robusto para PDFs de liquidación Cruz Blanca usando pdfplumber."""

import pdfplumber
import re
from typing import Dict, List, Optional, Tuple


class PDFParser:
    """Parser para extraer datos estructurados de PDFs de liquidación."""
    
    def __init__(self, pdf_path: str):
        """Inicializa el parser con un PDF."""
        self.pdf_path = pdf_path
        self.pdf = pdfplumber.open(pdf_path)
        self.text = self._extract_all_text()
        self.lines = self.text.split('\n')
    
    def _extract_all_text(self) -> str:
        """Extrae todo el texto del PDF."""
        return "\n".join(page.extract_text() for page in self.pdf.pages)
    
    def close(self):
        """Cierra el PDF."""
        self.pdf.close()
    
    # === HEADER EXTRACTION ===
    
    def extract_dates(self) -> Dict[str, Optional[str]]:
        """
        Extrae fechas de emisión y entrega.
        Returns: {"emision": "21/10/2025", "fecha_entrega": "18/03/2025"}
        """
        emision = re.search(r'Emisión\s*:\s*(\d{2}/\d{2}/\d{4})', self.text)
        fecha_entrega = re.search(r'Fecha Entrega:\s*(\d{2}/\d{2}/\d{4})', self.text)
        
        return {
            "emision": emision.group(1) if emision else None,
            "fecha_entrega": fecha_entrega.group(1) if fecha_entrega else None
        }
    
    def extract_cotizante(self) -> Dict[str, Optional[str]]:
        """
        Extrae RUT y nombre del cotizante.
        Pattern: "Cotizante : 11,119,228-6 PEDRO RENE ARANCIBIA CORTES"
        """
        match = re.search(
            r'Cotizante\s*:\s*([\d,]+\-[\dkK])\s+([A-ZÁÉÍÓÚÑ\s]+?)(?=\s+Fecha|$)',
            self.text,
            re.IGNORECASE
        )
        
        if match:
            return {
                "rut": match.group(1).strip(),
                "nombre": match.group(2).strip()
            }
        return {"rut": None, "nombre": None}
    
    def extract_paciente(self) -> Dict[str, Optional[str]]:
        """
        Extrae RUT y nombre del paciente.
        Pattern: "Paciente : 10,409,306-K MYRTA VIVIANA FUENZALIDA BORJA"
        """
        match = re.search(
            r'Paciente\s*:\s*([\d,]+\-[\dkK])\s+([A-ZÁÉÍÓÚÑ\s]+?)(?=\s+Prestador|$)',
            self.text,
            re.IGNORECASE
        )
        
        if match:
            return {
                "rut": match.group(1).strip(),
                "nombre": match.group(2).strip()
            }
        return {"rut": None, "nombre": None}
    
    def extract_plan_info(self) -> Dict:
        """
        Extrae información del plan y prestador.
        """
        plan_match = re.search(r'Plan:\s*(\S+)', self.text)
        spm_match = re.search(r'N°\s*SPM\s*:\s*(\d+)', self.text)
        inicio_match = re.search(r'Inicio Hosp\.\s*:\s*(\d{2}/\d{2}/\d{4})', self.text)
        estado_match = re.search(r'Estado:\s*(\w+)', self.text)
        
        # Flags booleanos
        ges_match = re.search(r'Tiene Gastos GES\s*:\s*(SI|NO)', self.text, re.IGNORECASE)
        caec_match = re.search(r'Tiene Gastos CAEC\s*:\s*(SI|NO)', self.text, re.IGNORECASE)
        urgencia_match = re.search(r'Es Ley de Urgencia\s*:\s*(SI|NO)', self.text, re.IGNORECASE)
        
        # Prestador (puede estar en múltiples líneas, hasta "Plan:")
        prestador = None
        prest_start = self.text.find('Prestador')
        if prest_start != -1:
            # Buscar desde "Prestador :" hasta la siguiente sección
            prest_section = self.text[prest_start:prest_start+200]
            # Extraer hasta "Plan:" o "Suc. Origen"
            prest_match = re.search(r'Prestador\s*:\s*(.+?)(?=Plan:|Suc\. Origen)', prest_section, re.DOTALL)
            if prest_match:
                # Limpiar saltos de línea y espacios extras
                prestador = ' '.join(prest_match.group(1).split()).strip()
        
        sucursal_match = re.search(r'Suc\. Origen\.\s*:\s*(.+?)(?=\n|$)', self.text)
        tramita_match = re.search(r'Tramitado Por:\s*(\w+)', self.text)
        origen_match = re.search(r'Origen\s*:\s*(.+?)(?=\s+Tramitado|$)', self.text)
        
        return {
            "codigo": plan_match.group(1) if plan_match else None,
            "n_spm": spm_match.group(1) if spm_match else None,
            "inicio_hospitalizacion": inicio_match.group(1) if inicio_match else None,
            "estado": estado_match.group(1) if estado_match else None,
            "tiene_gastos_ges": ges_match.group(1).upper() == "SI" if ges_match else False,
            "tiene_gastos_caec": caec_match.group(1).upper() == "SI" if caec_match else False,
            "es_ley_urgencia": urgencia_match.group(1).upper() == "SI" if urgencia_match else False,
            "prestador": prestador,
            "sucursal_origen": sucursal_match.group(1).strip() if sucursal_match else None,
            "tramita_por": tramita_match.group(1) if tramita_match else None,
            "origen": origen_match.group(1).strip() if origen_match else None
        }
    
    # === TABLES EXTRACTION ===
    
    def extract_detalle_tables(self) -> List[Dict]:
        """
        Extrae tablas de detalle (Hotelería y/o Exámenes).
        Returns: Lista de secciones con items y subtotales.
        """
        secciones = []
        
        # Buscar "Detalle Hoteleria"
        hoteleria = self._extract_hoteleria()
        if hoteleria:
            secciones.append(hoteleria)
        
        # Buscar "Detalle Exámenes y Procedimientos"
        examenes = self._extract_examenes()
        if examenes:
            secciones.append(examenes)
        
        return secciones
    
    def _extract_hoteleria(self) -> Optional[Dict]:
        """Extrae sección de Hotelería."""
        # Encontrar inicio y fin de la sección
        start_idx = None
        end_idx = None
        
        for i, line in enumerate(self.lines):
            if 'Detalle Hoteleria' in line:
                start_idx = i
            if start_idx and 'SubTotal Hoteleria' in line:
                end_idx = i
                break
        
        if not start_idx:
            return None
        
        # Extraer items (líneas entre header y subtotal)
        items = []
        for i in range(start_idx + 2, end_idx if end_idx else len(self.lines)):
            line = self.lines[i].strip()
            if not line or 'SubTotal' in line:
                break
            
            item = self._parse_detail_line(line)
            if item:
                items.append(item)
        
        # Extraer subtotal
        subtotal = self._extract_subtotal_hoteleria()
        
        return {
            "seccion": "Hoteleria",
            "items": items,
            "subtotal": subtotal
        }
    
    def _extract_examenes(self) -> Optional[Dict]:
        """Extrae sección de Exámenes y Procedimientos."""
        start_idx = None
        end_idx = None
        
        for i, line in enumerate(self.lines):
            # Solo asignar start_idx una vez
            if start_idx is None and ('Detalle Exámenes' in line or line.startswith('Detalle Exámenes')):
                start_idx = i
            # Buscar línea de subtotal (puede ser "SubTotal Exámenes" o "SubTotal Exámenes y Procedimientos")
            if start_idx is not None and line.startswith('SubTotal Exámenes'):
                end_idx = i
                break
        
        if not start_idx:
            return None
        
        items = []
        # Parsear líneas entre header y subtotal
        end_range = end_idx if end_idx else len(self.lines)
        for i in range(start_idx + 2, end_range):
            line = self.lines[i].strip()
            if not line:
                continue
            # Detectar inicio de subtotal
            if line.startswith('SubTotal'):
                break
            
            item = self._parse_detail_line(line)
            if item:
                items.append(item)
        
        subtotal = self._extract_subtotal_examenes()
        
        return {
            "seccion": "ExamenesYProcedimientos",
            "items": items,
            "subtotal": subtotal
        }
    
    def _parse_detail_line(self, line: str) -> Optional[Dict]:
        """
        Parsea una línea de detalle.
        Ejemplo: "15 02.01.001 0 DIA CAMA DE HOSPITALIZACION... 551 $ 313,937 $ 4,709,055 $ 1,612,140 34.23 % $ 3,096,915 $ 0 $ 0 CA 84570 BO 88701561 NO"
        """
        if not line:
            return None
        
        # Regex para parsear la línea
        # Patrón: cantidad código item descripción grupo val_unit val_tot bonif %plan caec seguro copago tc folio_gc td folio_br min_fonasa
        # Nota: folio_gc puede ser número o "---"
        pattern = r'^(\d+)\s+([\d.]+)\s+(\d+)\s+(.+?)\s+(\d+)\s+\$\s*([\d,]+)\s+\$\s*([\d,]+)\s+\$\s*([\d,]+)\s+([\d.]+)\s*%\s+\$\s*([\d,]+)\s+\$\s*([\d,]+)\s+\$\s*([\d,]+)\s+(\w+)\s+([\d\-]+)\s+(\w+)\s+([\d]+)\s+(SI|NO)$'
        
        match = re.match(pattern, line)
        if not match:
            return None
        
        return {
            "cantidad": int(match.group(1)),
            "codigo": match.group(2),
            "item": match.group(3),
            "descripcion": match.group(4).strip(),
            "grupo_cobertura": int(match.group(5)),
            "valor_unitario": self._parse_amount(match.group(6)),
            "valor_total": self._parse_amount(match.group(7)),
            "bonificacion": self._parse_amount(match.group(8)),
            "porcentaje_plan": float(match.group(9)) / 100.0,
            "caec": self._parse_amount(match.group(10)),
            "seguro": self._parse_amount(match.group(11)),
            "copago": self._parse_amount(match.group(12)),
            "tc": match.group(13),
            "folio_gc": match.group(14),
            "td": match.group(15),
            "folio_br": match.group(16),
            "min_fonasa": match.group(17).upper() == "SI"
        }
    
    def _extract_subtotal_hoteleria(self) -> Dict:
        """Extrae subtotal de hotelería."""
        for line in self.lines:
            if 'SubTotal Hoteleria' in line:
                # Siguiente línea tiene los montos
                idx = self.lines.index(line)
                if idx + 1 < len(self.lines):
                    amounts_line = self.lines[idx + 1]
                    return self._parse_subtotal_line(amounts_line)
        
        return self._empty_subtotal()
    
    def _extract_subtotal_examenes(self) -> Dict:
        """Extrae subtotal de exámenes."""
        for i, line in enumerate(self.lines):
            if line.startswith('SubTotal Exámenes'):
                # Puede tener los montos en la misma línea o en la siguiente
                if '$' in line:
                    # Montos en la misma línea
                    return self._parse_subtotal_line(line)
                elif i + 1 < len(self.lines):
                    # Montos en la siguiente línea
                    amounts_line = self.lines[i + 1]
                    return self._parse_subtotal_line(amounts_line)
        
        return self._empty_subtotal()
    
    def _parse_subtotal_line(self, line: str) -> Dict:
        """
        Parsea línea de subtotal.
        Ejemplo: "$ 4,709,055 $ 1,612,140 $ 3,096,915 $ 0 $ 0"
        """
        amounts = re.findall(r'\$\s*([\d,]+)', line)
        if len(amounts) >= 5:
            return {
                "valor_total": self._parse_amount(amounts[0]),
                "bonificacion": self._parse_amount(amounts[1]),
                "caec": self._parse_amount(amounts[2]),
                "seguro": self._parse_amount(amounts[3]),
                "copago": self._parse_amount(amounts[4])
            }
        return self._empty_subtotal()
    
    def _empty_subtotal(self) -> Dict:
        """Subtotal vacío."""
        return {
            "valor_total": 0,
            "bonificacion": 0,
            "caec": 0,
            "seguro": 0,
            "copago": 0
        }
    
    # === RESUMEN EXTRACTION ===
    
    def extract_resumen(self) -> Dict:
        """Extrae sección de resumen."""
        num_prestaciones = self._extract_numero_prestaciones()
        filas = self._extract_resumen_filas()
        desglose = self._extract_desglose_bonificado()
        
        return {
            "numero_prestaciones": num_prestaciones,
            "moneda": "CLP",
            "filas": filas,
            "desglose_bonificado": desglose
        }
    
    def _extract_numero_prestaciones(self) -> int:
        """Extrae número de prestaciones."""
        match = re.search(r'Número de Prestaciones:\s*(\d+)', self.text)
        return int(match.group(1)) if match else 0
    
    def _extract_resumen_filas(self) -> Dict:
        """
        Extrae filas Bono, Reembolso, Totales del resumen.
        Solo captura las líneas dentro de la sección Resumen (antes de "Total Bonificado").
        """
        bono = None
        reembolso = None
        totales = None
        
        # Encontrar límites de la sección Resumen
        resumen_start = None
        resumen_end = None
        
        for i, line in enumerate(self.lines):
            if 'Resumen:' in line:
                resumen_start = i
            # Buscar "Total Bonificado (1)" como línea independiente (sección siguiente)
            if resumen_start and line.strip() == 'Total Bonificado (1)':
                resumen_end = i
                break
        
        if not resumen_start:
            return {
                "bono": self._empty_resumen_row(),
                "reembolso": self._empty_resumen_row(),
                "totales": self._empty_resumen_row()
            }
        
        # Parsear solo líneas dentro del rango
        end_idx = resumen_end if resumen_end else len(self.lines)
        for i in range(resumen_start, end_idx):
            line = self.lines[i]
            
            if line.startswith('Bono'):
                bono = self._parse_resumen_row(line)
            elif line.startswith('Reembolso'):
                reembolso = self._parse_resumen_row(line)
            elif line.startswith('Totales'):
                totales = self._parse_resumen_row(line)
        
        return {
            "bono": bono or self._empty_resumen_row(),
            "reembolso": reembolso or self._empty_resumen_row(),
            "totales": totales or self._empty_resumen_row()
        }
    
    def _parse_resumen_row(self, line: str) -> Dict:
        """
        Parsea fila de resumen.
        Ejemplo: "Bono $ 4,709,055 $ 1,612,140 $ 3,096,915 $ 0 $ 0 -------"
        """
        amounts = re.findall(r'\$\s*([\d,]+)', line)
        
        # Cheque puede ser "-------" o un monto
        cheque = None
        if '-------' not in line and len(amounts) >= 6:
            cheque = self._parse_amount(amounts[5])
        
        if len(amounts) >= 5:
            return {
                "prestacion": self._parse_amount(amounts[0]),
                "bonificado": self._parse_amount(amounts[1]),
                "caec": self._parse_amount(amounts[2]),
                "seguro": self._parse_amount(amounts[3]),
                "copago_afiliado": self._parse_amount(amounts[4]),
                "cheque": cheque
            }
        
        return self._empty_resumen_row()
    
    def _empty_resumen_row(self) -> Dict:
        """Fila de resumen vacía."""
        return {
            "prestacion": 0,
            "bonificado": 0,
            "caec": 0,
            "seguro": 0,
            "copago_afiliado": 0,
            "cheque": None
        }
    
    def _extract_desglose_bonificado(self) -> Dict:
        """
        Extrae tabla "Total Bonificado (1)".
        """
        plan_comp = None
        ges = None
        ges_caec = None
        totales_desglose = None
        
        # Buscar sección
        start_idx = None
        for i, line in enumerate(self.lines):
            if 'Total Bonificado (1)' in line:
                start_idx = i
                break
        
        if not start_idx:
            return self._empty_desglose()
        
        # Parsear líneas siguientes
        for i in range(start_idx + 1, min(start_idx + 10, len(self.lines))):
            line = self.lines[i]
            
            if 'Plan Complementario' in line:
                amounts = re.findall(r'\$\s*([\d,]+)', line)
                if len(amounts) >= 2:
                    plan_comp = {
                        "gasto": self._parse_amount(amounts[0]),
                        "bonificado": self._parse_amount(amounts[1])
                    }
            
            elif line.strip().startswith('GES-CAEC'):
                amounts = re.findall(r'\$\s*([\d,]+)', line)
                if len(amounts) >= 2:
                    ges_caec = {
                        "gasto": self._parse_amount(amounts[0]),
                        "bonificado": self._parse_amount(amounts[1])
                    }
            
            elif line.strip().startswith('GES') and 'CAEC' not in line:
                amounts = re.findall(r'\$\s*([\d,]+)', line)
                if len(amounts) >= 2:
                    ges = {
                        "gasto": self._parse_amount(amounts[0]),
                        "bonificado": self._parse_amount(amounts[1])
                    }
            
            elif 'Totales' in line:
                amounts = re.findall(r'\$\s*([\d,]+)', line)
                if len(amounts) >= 2:
                    totales_desglose = {
                        "gasto": self._parse_amount(amounts[0]),
                        "bonificado": self._parse_amount(amounts[1])
                    }
        
        return {
            "plan_complementario": plan_comp or {"gasto": 0, "bonificado": 0},
            "ges": ges or {"gasto": 0, "bonificado": 0},
            "ges_caec": ges_caec or {"gasto": 0, "bonificado": 0},
            "totales": totales_desglose or {"gasto": 0, "bonificado": 0}
        }
    
    def _empty_desglose(self) -> Dict:
        """Desglose vacío."""
        return {
            "plan_complementario": {"gasto": 0, "bonificado": 0},
            "ges": {"gasto": 0, "bonificado": 0},
            "ges_caec": {"gasto": 0, "bonificado": 0},
            "totales": {"gasto": 0, "bonificado": 0}
        }
    
    # === UTILITIES ===
    
    def _parse_amount(self, value) -> int:
        """
        Parsea monto: "$125,880" → 125880
        """
        if value is None:
            return 0
        s = str(value).replace('$', '').replace(',', '').replace('.', '').strip()
        if not s or s == '0' or s in ['---', '-------']:
            return 0
        try:
            return int(s)
        except ValueError:
            return 0

