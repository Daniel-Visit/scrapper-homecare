"""
API REST para el microservicio de scraping.

Este paquete expone endpoints REST para gatillar procesos de scraping
y consultar archivos generados. El worker RQ ejecuta el pipeline completo:
scraping → extracción → reporte → subida a SFTP.
"""

__version__ = "1.0.0"

