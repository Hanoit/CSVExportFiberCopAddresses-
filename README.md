# CSVExportFiberCopAddresses-
Automated CSV Export – FiberCop Addresses 


**# Descripción de la Herramienta de Exportación de Direcciones Fibercop

Esta herramienta permite exportar direcciones desde el visor de Fibercop hacia un archivo `.csv`, sin límite máximo de selección. A continuación, se describen las funcionalidades, configuraciones y reglas de negocio para la generación del archivo resultante.

---

## Funcionalidad Principal

1. **Selección de polígonos**  
   - El usuario selecciona un polígono en el visor de Fibercop.  
   - Todas las direcciones dentro de ese polígono se exportan a un archivo `.csv`.  
   - Las coordenadas XY se actualizan según la ubicación de cada dirección.

2. **Nombres de columnas**  
   - Las cabeceras de columna del archivo `.csv` **deben ser idénticas** a las de Esri.  
   - Los valores de dominio deben exportarse como **texto**, no como identificador numérico.

---

## Configuración en el Visor WebApp

- Se recomienda que la configuración de la herramienta (o el mapeo de campos) pueda definirse en la fase de implementación dentro de la aplicación WebApp del visor.  
- Esto facilita la adaptabilidad del proceso y reduce la necesidad de cambios de código.

---

## Fusión de Campos Duplicados

Existen columnas con el mismo tipo de información, en las que una proviene del cliente y otra se genera tras encontrar discrepancias (campo `_NEW`). Ambas deben fusionarse en un único campo en el archivo de salida. A continuación, se listan los pares a fusionar y el nombre final sugerido:

| Campos Originales             | Campo de Salida    |
|-------------------------------|---------------------|
| `Civico` / `Civico_New`       | **HouseNumber**     |
| `Barrato` / `Barrato_New`     | **Addition**        |
| `Indirizzo` / `Indirizo_New`  | **Address**         |
| `Particella` / `Particell_1` / `particella_new` | **Preposition** |
| `Via` / `Via_New`             | **Streetname**      |

**Regla de Fusión**  
- Si el campo `_NEW` está **relleno**, se usa su valor en el archivo de salida.  
- Si el campo `_NEW` **está vacío**, se usa el valor original.

---

## Creación de un Campo Adicional: “Units”

Se deben comparar los campos `TOT_UNI_IM` y `AL_TOTAL`, y asignar a la columna “Units” el valor más alto entre ambos.

- **Ejemplo**:  
  - `TOT_UNI_IM = 8`  
  - `AL_TOTAL = 5`  
  - **“Units”** = `8`

---

## Reemplazo de Valores “SNC” u “0” en el HouseNumber

Si en la fusión de `Civico` / `Civico_New` el resultado es “SNC” o `0`, dicho valor debe sustituirse por un número único que garantice que **cada punto de dirección tenga una combinación irrepetible** de (Streetname / HouseNumber / Addition).  
- Ningún punto de dirección debe quedar con la misma tripleta (Streetname / HouseNumber / Addition).

---

## Exclusión de Registros con Units = 0

Todos los puntos de dirección que resulten con el valor total de “Units” = `0` **no** se incluirán en el archivo `.csv` final.

---

## Flujo de Trabajo Resumido

1. **Seleccionar** un polígono en el visor Fibercop.  
2. **Ejecutar** la herramienta de exportación.  
3. **Obtener** todas las direcciones dentro del polígono y fusionar los campos `_NEW` si aplica.  
4. **Calcular** el campo “Units” con el valor máximo entre `TOT_UNI_IM` y `AL_TOTAL`.  
5. **Reemplazar** valores “SNC” o `0` en el campo HouseNumber por un número único.  
6. **Excluir** direcciones con “Units” = `0`.  
7. **Exportar** el resultado a `.csv` con las cabeceras de Esri.

---

## Notas Finales

- Asegúrate de que los valores de dominio se exporten siempre como **texto**.  
- Verifica que cada dirección tenga un identificador de HouseNumber único si ocurre el caso “SNC” o `0`.  
- La herramienta debe ser lo suficientemente flexible para permitir configuraciones adicionales desde el visor WebApp según las necesidades del proyecto.

---
**
