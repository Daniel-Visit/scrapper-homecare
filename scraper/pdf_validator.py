"""Validador autónomo de JSONs extraídos contra PDF original y schema."""

import jsonschema
from scraper.json_schema import LIQUIDACION_SCHEMA
from scraper.pdf_parser import PDFParser
from typing import Dict, List


class PDFValidator:
    """Valida JSON generado contra schema y contenido del PDF original."""
    
    def validate(self, pdf_path: str, json_data: Dict) -> Dict:
        """
        Validación completa: schema + contenido + consistencia.
        
        Returns: {
            "is_valid": bool,
            "total_errors": int,
            "errors": [{"section": str, "field": str, "error": str, ...}]
        }
        """
        errors = []
        
        # 1. Validar JSON Schema
        schema_errors = self._validate_schema(json_data)
        errors.extend(schema_errors)
        
        # 2. Validar contra contenido del PDF
        parser = PDFParser(pdf_path)
        try:
            content_errors = self._validate_content(parser, json_data)
            errors.extend(content_errors)
        finally:
            parser.close()
        
        # 3. Validar consistencia numérica
        consistency_errors = self._validate_numeric_consistency(json_data)
        errors.extend(consistency_errors)
        
        return {
            "is_valid": len(errors) == 0,
            "total_errors": len(errors),
            "errors": errors
        }
    
    def _validate_schema(self, data: Dict) -> List[Dict]:
        """Valida contra JSON Schema."""
        errors = []
        try:
            jsonschema.validate(instance=data, schema=LIQUIDACION_SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append({
                "section": "schema",
                "field": ".".join(str(p) for p in e.path) if e.path else "root",
                "error": e.message,
                "expected": None,
                "actual": None
            })
        except jsonschema.SchemaError as e:
            errors.append({
                "section": "schema",
                "field": "schema_definition",
                "error": f"Schema inválido: {e.message}",
                "expected": None,
                "actual": None
            })
        
        return errors
    
    def _validate_content(self, parser: PDFParser, json_data: Dict) -> List[Dict]:
        """
        Valida que los datos del JSON coincidan con el PDF original.
        Compara:
        - Fechas
        - RUTs y nombres
        - Montos (subtotales, totales)
        - Número de items
        """
        errors = []
        
        # Validar header/document
        errors.extend(self._validate_dates(parser, json_data))
        errors.extend(self._validate_persons(parser, json_data))
        errors.extend(self._validate_plan_info(parser, json_data))
        
        # Validar detalle
        errors.extend(self._validate_detalle(parser, json_data))
        
        # Validar resumen
        errors.extend(self._validate_resumen(parser, json_data))
        
        return errors
    
    def _validate_dates(self, parser: PDFParser, json_data: Dict) -> List[Dict]:
        """Valida fechas."""
        errors = []
        dates_pdf = parser.extract_dates()
        
        # Emisión
        emision_pdf = self._normalize_date(dates_pdf.get("emision"))
        emision_json = json_data["document"]["emision"]
        if emision_pdf != emision_json:
            errors.append({
                "section": "document",
                "field": "emision",
                "error": "Fecha de emisión no coincide con PDF",
                "expected": dates_pdf.get("emision"),
                "actual": emision_json
            })
        
        # Fecha entrega
        entrega_pdf = self._normalize_date(dates_pdf.get("fecha_entrega"))
        entrega_json = json_data["document"]["fecha_entrega"]
        if entrega_pdf != entrega_json:
            errors.append({
                "section": "document",
                "field": "fecha_entrega",
                "error": "Fecha de entrega no coincide con PDF",
                "expected": dates_pdf.get("fecha_entrega"),
                "actual": entrega_json
            })
        
        return errors
    
    def _validate_persons(self, parser: PDFParser, json_data: Dict) -> List[Dict]:
        """Valida RUTs y nombres de cotizante y paciente."""
        errors = []
        
        # Cotizante
        cotizante_pdf = parser.extract_cotizante()
        rut_pdf = self._normalize_rut(cotizante_pdf.get("rut"))
        rut_json = json_data["cotizante"]["rut"]
        
        if rut_pdf != rut_json:
            errors.append({
                "section": "cotizante",
                "field": "rut",
                "error": "RUT no coincide con PDF",
                "expected": cotizante_pdf.get("rut"),
                "actual": rut_json
            })
        
        # Paciente
        paciente_pdf = parser.extract_paciente()
        rut_pdf = self._normalize_rut(paciente_pdf.get("rut"))
        rut_json = json_data["paciente"]["rut"]
        
        if rut_pdf != rut_json:
            errors.append({
                "section": "paciente",
                "field": "rut",
                "error": "RUT no coincide con PDF",
                "expected": paciente_pdf.get("rut"),
                "actual": rut_json
            })
        
        return errors
    
    def _validate_plan_info(self, parser: PDFParser, json_data: Dict) -> List[Dict]:
        """Valida información del plan."""
        errors = []
        plan_pdf = parser.extract_plan_info()
        plan_json = json_data["plan"]
        
        # Validar campos clave
        if plan_pdf.get("codigo") != plan_json.get("codigo"):
            errors.append({
                "section": "plan",
                "field": "codigo",
                "error": "Código de plan no coincide",
                "expected": plan_pdf.get("codigo"),
                "actual": plan_json.get("codigo")
            })
        
        if plan_pdf.get("n_spm") != plan_json.get("n_spm"):
            errors.append({
                "section": "plan",
                "field": "n_spm",
                "error": "N° SPM no coincide",
                "expected": plan_pdf.get("n_spm"),
                "actual": plan_json.get("n_spm")
            })
        
        return errors
    
    def _validate_detalle(self, parser: PDFParser, json_data: Dict) -> List[Dict]:
        """Valida tablas de detalle (items y subtotales)."""
        errors = []
        detalle_pdf = parser.extract_detalle_tables()
        detalle_json = json_data["detalle"]
        
        # Validar número de secciones
        if len(detalle_pdf) != len(detalle_json):
            errors.append({
                "section": "detalle",
                "field": "secciones_count",
                "error": "Número de secciones no coincide",
                "expected": len(detalle_pdf),
                "actual": len(detalle_json)
            })
            return errors  # No continuar si no coincide la estructura
        
        # Validar cada sección
        for i, (sec_pdf, sec_json) in enumerate(zip(detalle_pdf, detalle_json)):
            # Validar subtotales
            subtotal_pdf = sec_pdf["subtotal"]
            subtotal_json = sec_json["subtotal"]
            
            for field in ["valor_total", "bonificacion", "caec", "seguro", "copago"]:
                if subtotal_pdf[field] != subtotal_json[field]:
                    errors.append({
                        "section": f"detalle.{sec_json['seccion']}",
                        "field": f"subtotal.{field}",
                        "error": f"Subtotal {field} no coincide con PDF",
                        "expected": subtotal_pdf[field],
                        "actual": subtotal_json[field]
                    })
            
            # Validar número de items
            if len(sec_pdf["items"]) != len(sec_json["items"]):
                errors.append({
                    "section": f"detalle.{sec_json['seccion']}",
                    "field": "items_count",
                    "error": "Número de items no coincide",
                    "expected": len(sec_pdf["items"]),
                    "actual": len(sec_json["items"])
                })
        
        return errors
    
    def _validate_resumen(self, parser: PDFParser, json_data: Dict) -> List[Dict]:
        """Valida sección de resumen."""
        errors = []
        resumen_pdf = parser.extract_resumen()
        resumen_json = json_data["resumen"]
        
        # Validar número de prestaciones
        if resumen_pdf["numero_prestaciones"] != resumen_json["numero_prestaciones"]:
            errors.append({
                "section": "resumen",
                "field": "numero_prestaciones",
                "error": "Número de prestaciones no coincide",
                "expected": resumen_pdf["numero_prestaciones"],
                "actual": resumen_json["numero_prestaciones"]
            })
        
        # Validar filas (bono, reembolso, totales)
        for fila_name in ["bono", "reembolso", "totales"]:
            fila_pdf = resumen_pdf["filas"][fila_name]
            fila_json = resumen_json["filas"][fila_name]
            
            for field in ["prestacion", "bonificado", "caec", "seguro", "copago_afiliado"]:
                if fila_pdf[field] != fila_json[field]:
                    errors.append({
                        "section": "resumen",
                        "field": f"filas.{fila_name}.{field}",
                        "error": f"{fila_name}.{field} no coincide con PDF",
                        "expected": fila_pdf[field],
                        "actual": fila_json[field]
                    })
        
        return errors
    
    def _validate_numeric_consistency(self, json_data: Dict) -> List[Dict]:
        """Valida que las ecuaciones de consistencia sean True."""
        errors = []
        consistencia = json_data["resumen"]["consistencia"]
        ecuaciones = consistencia["ecuaciones"]
        
        for eq_name, is_valid in ecuaciones.items():
            if not is_valid:
                errors.append({
                    "section": "consistencia",
                    "field": eq_name,
                    "error": f"Ecuación {eq_name} no se cumple",
                    "expected": True,
                    "actual": False
                })
        
        return errors
    
    # === HELPERS ===
    
    def _normalize_rut(self, rut: str) -> str:
        """Normaliza RUT para comparación."""
        if not rut:
            return ""
        return rut.replace('.', '').replace(',', '').replace(' ', '').upper()
    
    def _normalize_date(self, date_str: str) -> str:
        """Normaliza fecha a formato ISO."""
        if not date_str:
            return None
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None



