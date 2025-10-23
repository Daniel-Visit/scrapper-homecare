"""JSON Schema para validación de extractos de liquidación."""

LIQUIDACION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Detalle PDF (Liquidación Programa Médico)",
    "type": "object",
    "required": ["document", "cotizante", "paciente", "plan", "detalle", "resumen"],
    "properties": {
        "document": {
            "type": "object",
            "required": ["tipo", "emision", "fecha_entrega", "isapre", "estado", "es_ley_urgencia", "origen"],
            "properties": {
                "tipo": {"type": "string", "const": "LIQUIDACION_PROGRAMA_MEDICO"},
                "emision": {"type": "string", "format": "date"},
                "fecha_entrega": {"type": "string", "format": "date"},
                "isapre": {"type": "string"},
                "estado": {"type": "string"},
                "es_ley_urgencia": {"type": "boolean"},
                "origen": {"type": "string"},
                "noveno": {"type": ["string", "null"]}
            },
            "additionalProperties": False
        },
        "cotizante": {
            "type": "object",
            "required": ["rut", "nombre"],
            "properties": {
                "rut": {"type": "string"},
                "nombre": {"type": "string"}
            },
            "additionalProperties": False
        },
        "paciente": {
            "type": "object",
            "required": ["rut", "nombre"],
            "properties": {
                "rut": {"type": "string"},
                "nombre": {"type": "string"}
            },
            "additionalProperties": False
        },
        "plan": {
            "type": "object",
            "required": [
                "codigo", "n_spm", "inicio_hospitalizacion",
                "tiene_gastos_ges", "tiene_gastos_caec", "tramita_por", "prestador"
            ],
            "properties": {
                "codigo": {"type": "string"},
                "n_spm": {"type": "string"},
                "inicio_hospitalizacion": {"type": "string", "format": "date"},
                "tiene_gastos_ges": {"type": "boolean"},
                "tiene_gastos_caec": {"type": "boolean"},
                "tramita_por": {"type": "string"},
                "prestador": {"type": "string"},
                "sucursal_origen": {"type": ["string", "null"]}
            },
            "additionalProperties": False
        },
        "detalle": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["seccion", "items", "subtotal"],
                "properties": {
                    "seccion": {"type": "string"},
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": [
                                "cantidad", "codigo", "item", "descripcion", "grupo_cobertura",
                                "valor_unitario", "valor_total", "bonificacion", "porcentaje_plan",
                                "caec", "seguro", "copago", "tc", "td", "folio_br", "min_fonasa"
                            ],
                            "properties": {
                                "cantidad": {"type": "integer", "minimum": 0},
                                "codigo": {"type": "string"},
                                "item": {"type": ["string", "integer"]},
                                "descripcion": {"type": "string"},
                                "grupo_cobertura": {"type": "integer"},
                                "valor_unitario": {"type": "integer", "minimum": 0},
                                "valor_total": {"type": "integer", "minimum": 0},
                                "bonificacion": {"type": "integer", "minimum": 0},
                                "porcentaje_plan": {"type": "number", "minimum": 0, "maximum": 1},
                                "caec": {"type": "integer", "minimum": 0},
                                "seguro": {"type": "integer", "minimum": 0},
                                "copago": {"type": "integer", "minimum": 0},
                                "tc": {"type": "string"},
                                "folio_gc": {"type": ["string", "null"]},
                                "td": {"type": "string"},
                                "folio_br": {"type": "string"},
                                "min_fonasa": {"type": "boolean"}
                            },
                            "additionalProperties": False
                        }
                    },
                    "subtotal": {
                        "type": "object",
                        "required": ["valor_total", "bonificacion", "caec", "seguro", "copago"],
                        "properties": {
                            "valor_total": {"type": "integer", "minimum": 0},
                            "bonificacion": {"type": "integer", "minimum": 0},
                            "caec": {"type": "integer", "minimum": 0},
                            "seguro": {"type": "integer", "minimum": 0},
                            "copago": {"type": "integer", "minimum": 0}
                        },
                        "additionalProperties": False
                    }
                },
                "additionalProperties": False
            }
        },
        "resumen": {
            "type": "object",
            "required": ["numero_prestaciones", "moneda", "filas", "porcentajes", "desglose_bonificado", "consistencia"],
            "properties": {
                "numero_prestaciones": {"type": "integer", "minimum": 0},
                "moneda": {"type": "string", "const": "CLP"},
                "filas": {
                    "type": "object",
                    "required": ["bono", "reembolso", "totales"],
                    "properties": {
                        "bono": {
                            "type": "object",
                            "required": ["prestacion", "bonificado", "caec", "seguro", "copago_afiliado", "cheque"],
                            "properties": {
                                "prestacion": {"type": "integer", "minimum": 0},
                                "bonificado": {"type": "integer", "minimum": 0},
                                "caec": {"type": "integer", "minimum": 0},
                                "seguro": {"type": "integer", "minimum": 0},
                                "copago_afiliado": {"type": "integer", "minimum": 0},
                                "cheque": {"type": ["integer", "null"], "minimum": 0}
                            },
                            "additionalProperties": False
                        },
                        "reembolso": {
                            "type": "object",
                            "required": ["prestacion", "bonificado", "caec", "seguro", "copago_afiliado", "cheque"],
                            "properties": {
                                "prestacion": {"type": "integer", "minimum": 0},
                                "bonificado": {"type": "integer", "minimum": 0},
                                "caec": {"type": "integer", "minimum": 0},
                                "seguro": {"type": "integer", "minimum": 0},
                                "copago_afiliado": {"type": "integer", "minimum": 0},
                                "cheque": {"type": ["integer", "null"], "minimum": 0}
                            },
                            "additionalProperties": False
                        },
                        "totales": {
                            "type": "object",
                            "required": ["prestacion", "bonificado", "caec", "seguro", "copago_afiliado", "cheque"],
                            "properties": {
                                "prestacion": {"type": "integer", "minimum": 0},
                                "bonificado": {"type": "integer", "minimum": 0},
                                "caec": {"type": "integer", "minimum": 0},
                                "seguro": {"type": "integer", "minimum": 0},
                                "copago_afiliado": {"type": "integer", "minimum": 0},
                                "cheque": {"type": ["integer", "null"], "minimum": 0}
                            },
                            "additionalProperties": False
                        }
                    },
                    "additionalProperties": False
                },
                "porcentajes": {
                    "type": "object",
                    "required": ["bonificado_sobre_prestacion", "caec_sobre_prestacion", "seguro_sobre_prestacion"],
                    "properties": {
                        "bonificado_sobre_prestacion": {"type": "number", "minimum": 0, "maximum": 1},
                        "caec_sobre_prestacion": {"type": "number", "minimum": 0, "maximum": 1},
                        "seguro_sobre_prestacion": {"type": "number", "minimum": 0, "maximum": 1}
                    },
                    "additionalProperties": False
                },
                "desglose_bonificado": {
                    "type": "object",
                    "required": ["plan_complementario", "ges", "ges_caec", "totales"],
                    "properties": {
                        "plan_complementario": {
                            "type": "object",
                            "required": ["gasto", "bonificado"],
                            "properties": {
                                "gasto": {"type": "integer", "minimum": 0},
                                "bonificado": {"type": "integer", "minimum": 0}
                            },
                            "additionalProperties": False
                        },
                        "ges": {
                            "type": "object",
                            "required": ["gasto", "bonificado"],
                            "properties": {
                                "gasto": {"type": "integer", "minimum": 0},
                                "bonificado": {"type": "integer", "minimum": 0}
                            },
                            "additionalProperties": False
                        },
                        "ges_caec": {
                            "type": "object",
                            "required": ["gasto", "bonificado"],
                            "properties": {
                                "gasto": {"type": "integer", "minimum": 0},
                                "bonificado": {"type": "integer", "minimum": 0}
                            },
                            "additionalProperties": False
                        },
                        "totales": {
                            "type": "object",
                            "required": ["gasto", "bonificado"],
                            "properties": {
                                "gasto": {"type": "integer", "minimum": 0},
                                "bonificado": {"type": "integer", "minimum": 0}
                            },
                            "additionalProperties": False
                        }
                    },
                    "additionalProperties": False
                },
                "consistencia": {
                    "type": "object",
                    "required": ["ecuaciones", "copago_teorico", "diferencia_copago"],
                    "properties": {
                        "ecuaciones": {
                            "type": "object",
                            "required": [
                                "totales_igual_bono_mas_reembolso",
                                "prestacion_igual_suma_componentes",
                                "copago_teorico_igual_presentado"
                            ],
                            "properties": {
                                "totales_igual_bono_mas_reembolso": {"type": "boolean"},
                                "prestacion_igual_suma_componentes": {"type": "boolean"},
                                "copago_teorico_igual_presentado": {"type": "boolean"}
                            },
                            "additionalProperties": False
                        },
                        "copago_teorico": {"type": "integer"},
                        "diferencia_copago": {"type": "integer"}
                    },
                    "additionalProperties": False
                }
            },
            "additionalProperties": False
        }
    },
    "additionalProperties": False
}



