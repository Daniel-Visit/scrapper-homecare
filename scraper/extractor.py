"""Extractor de datos de PDFs - genera JSON estructurado según schema."""

from scraper.pdf_parser import PDFParser
from datetime import datetime
from typing import Dict, Optional


class PDFExtractor:
    """Genera JSON estructurado desde PDFs parseados."""
    
    def extract_from_file(self, pdf_path: str) -> Dict:
        """
        Extrae y normaliza datos de un PDF.
        Returns: Dict según schema JSON proporcionado.
        """
        parser = PDFParser(pdf_path)
        
        try:
            # Construir JSON estructurado
            data = {
                "document": self._build_document(parser),
                "cotizante": self._build_person(parser.extract_cotizante()),
                "paciente": self._build_person(parser.extract_paciente()),
                "plan": self._build_plan(parser),
                "detalle": parser.extract_detalle_tables(),
                "resumen": self._build_resumen(parser)
            }
            
            return data
        finally:
            parser.close()
    
    def _build_document(self, parser: PDFParser) -> Dict:
        """Construye sección document."""
        dates = parser.extract_dates()
        plan_info = parser.extract_plan_info()
        
        return {
            "tipo": "LIQUIDACION_PROGRAMA_MEDICO",
            "emision": self._normalize_date(dates.get("emision")),
            "fecha_entrega": self._normalize_date(dates.get("fecha_entrega")),
            "isapre": "CruzBlanca",
            "estado": plan_info.get("estado", ""),
            "es_ley_urgencia": plan_info.get("es_ley_urgencia", False),
            "origen": plan_info.get("origen", ""),
            "noveno": None  # Se extrae del PDF si está presente
        }
    
    def _build_person(self, person_data: Dict) -> Dict:
        """Normaliza datos de persona (cotizante/paciente)."""
        return {
            "rut": self._normalize_rut(person_data.get("rut", "")),
            "nombre": person_data.get("nombre", "").strip()
        }
    
    def _build_plan(self, parser: PDFParser) -> Dict:
        """Construye sección plan."""
        plan_info = parser.extract_plan_info()
        
        return {
            "codigo": plan_info.get("codigo", ""),
            "n_spm": plan_info.get("n_spm", ""),
            "inicio_hospitalizacion": self._normalize_date(plan_info.get("inicio_hospitalizacion")),
            "tiene_gastos_ges": plan_info.get("tiene_gastos_ges", False),
            "tiene_gastos_caec": plan_info.get("tiene_gastos_caec", False),
            "tramita_por": plan_info.get("tramita_por", ""),
            "prestador": plan_info.get("prestador", ""),
            "sucursal_origen": plan_info.get("sucursal_origen")
        }
    
    def _build_resumen(self, parser: PDFParser) -> Dict:
        """Construye sección resumen con cálculos adicionales."""
        resumen_raw = parser.extract_resumen()
        
        # Calcular porcentajes
        totales = resumen_raw["filas"]["totales"]
        prestacion = totales["prestacion"]
        
        if prestacion > 0:
            porcentajes = {
                "bonificado_sobre_prestacion": totales["bonificado"] / prestacion,
                "caec_sobre_prestacion": totales["caec"] / prestacion,
                "seguro_sobre_prestacion": totales["seguro"] / prestacion
            }
        else:
            porcentajes = {
                "bonificado_sobre_prestacion": 0.0,
                "caec_sobre_prestacion": 0.0,
                "seguro_sobre_prestacion": 0.0
            }
        
        # Calcular consistencia
        consistencia = self._calculate_consistency(resumen_raw["filas"])
        
        return {
            **resumen_raw,
            "porcentajes": porcentajes,
            "consistencia": consistencia
        }
    
    def _calculate_consistency(self, filas: Dict) -> Dict:
        """
        Valida ecuaciones de consistencia numérica.
        
        Ecuaciones:
        1. Totales = Bono + Reembolso (en cada columna)
        2. Prestación = Bonificado + CAEC + Seguro + Copago
        3. Copago teórico vs presentado
        """
        bono = filas["bono"]
        reembolso = filas["reembolso"]
        totales = filas["totales"]
        
        # Ecuación 1: Totales = Bono + Reembolso
        eq1 = (
            totales["prestacion"] == bono["prestacion"] + reembolso["prestacion"] and
            totales["bonificado"] == bono["bonificado"] + reembolso["bonificado"] and
            totales["caec"] == bono["caec"] + reembolso["caec"]
        )
        
        # Ecuación 2: Prestación = Bonificado + CAEC + Seguro + Copago
        prestacion_calculada = (
            totales["bonificado"] +
            totales["caec"] +
            totales["seguro"] +
            totales["copago_afiliado"]
        )
        # Tolerancia de $10 por redondeos
        eq2 = abs(totales["prestacion"] - prestacion_calculada) <= 10
        
        # Ecuación 3: Copago teórico = presentado
        copago_teorico = (
            totales["prestacion"] -
            totales["bonificado"] -
            totales["caec"] -
            totales["seguro"]
        )
        eq3 = abs(copago_teorico - totales["copago_afiliado"]) <= 10
        
        return {
            "ecuaciones": {
                "totales_igual_bono_mas_reembolso": eq1,
                "prestacion_igual_suma_componentes": eq2,
                "copago_teorico_igual_presentado": eq3
            },
            "copago_teorico": copago_teorico,
            "diferencia_copago": copago_teorico - totales["copago_afiliado"]
        }
    
    # === NORMALIZACIÓN ===
    
    def _normalize_rut(self, rut_str: str) -> str:
        """
        Normaliza RUT: 12.696.942-2 → 12696942-2
        """
        if not rut_str:
            return ""
        return rut_str.replace('.', '').replace(',', '').replace(' ', '').upper()
    
    def _normalize_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Normaliza fecha: 21/10/2025 → 2025-10-21 (ISO 8601)
        """
        if not date_str:
            return None
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None
