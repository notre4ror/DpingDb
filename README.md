# DPingDb - Programa de Monitoreo de IPs con Ping

## Requisitos del Sistema

- Python 3.x instalado
- Librerías requeridas: `tkinter`, `mysql-connector`, `os`, `json`, `re`, `time`, `threading`, `sys`
- Base de datos MySQL existente (detalles configurables)
- Sistema operativo Windows o Linux

---
## Interacción con la Base de Datos

- **Tabla requerida**: Debe tener al menos una columna `ip_registro` (VARCHAR)

- Flujo:

   ```python
     
   def check_ip():
       db_ip = obtener_de_base_datos()
       ping_ip = ejecutar_ping()
       if db_ip != ping_ip:
           actualizar_base_datos(ping_ip)
   ```

---

## Manejo de Errores

1. **Conexión fallida** → Modo "Solo Ping" con notificación en GUI
2. **Directorio inválido** → Alerta y uso del directorio actual como predeterminado
3. **Formato JSON incorrecto** → Reiniciar configuración a valores base

---

## Uso Básico

1. Ejecutar `python3 dpingdb.py`
2. Configurar parámetros en la pestaña correspondiente
3. Iniciar monitoreo con el botón principal
4. Ver resultados históricos filtrando por criterios relevantes
