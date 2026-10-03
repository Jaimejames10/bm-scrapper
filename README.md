# Buscador de usuarios del backoffice

Aplicación web interna para buscar usuarios por `accountCode` en el backoffice Angular y mostrar:

- Usuario
- Código de cuenta
- Número de comprobante
- Fecha de comprobante

La automatización se realiza con Playwright. El navegador se ejecuta en el servidor y las credenciales no llegan al navegador del usuario final.

## Requisitos

- Python `3.13.6` o cualquier versión `3.13.x`.
- Acceso de red desde esta máquina al backoffice configurado en `SCRAPER_TARGET_URL`.
- Credenciales autorizadas para consultar el backoffice.

La versión local detectada durante la configuración es Python `3.13.15`. El proyecto declara `>=3.13,<3.14`, por lo que también es compatible con Python `3.13.6`.

## Instalación local

En PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
\.\.venv\Scripts\python.exe -m pip install -r requirements.txt
\.\.venv\Scripts\python.exe -m playwright install chromium
Copy-Item .env.example .env
```

Edita `.env` y coloca las credenciales reales autorizadas. El archivo `.env` está excluido de Git.

## Ejecución

```powershell
\.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abre `http://127.0.0.1:8000` en el navegador. El endpoint `http://127.0.0.1:8000/health` permite comprobar si Chromium está listo.

Para probar el backend:

```powershell
\.\.venv\Scripts\python.exe -m pytest
```

## Flujo automatizado

1. Abre la URL configurada.
2. Completa `#username` y `#password`.
3. Abre el menú Administración.
4. Entra a `#/admin/client` mediante el enlace Clientes.
5. Si Angular no renderiza el menú, usa la ruta directa como respaldo.
6. Completa `#accountCode` y pulsa Filtrar.
7. Espera los botones `button[title="Ver Detalle"]`.
8. Abre cada detalle y lee `#idaccount`, `#vaccountCode`, `#idcontractNumber` e `#idcontractDate`.

Cada consulta utiliza un contexto de navegador independiente para evitar compartir cookies o estado entre usuarios de la herramienta.

## Configuración

Las variables disponibles usan el prefijo `SCRAPER_`:

| Variable | Descripción |
| --- | --- |
| `SCRAPER_TARGET_URL` | URL de login del backoffice |
| `SCRAPER_USERNAME` | Usuario del backoffice |
| `SCRAPER_PASSWORD` | Contraseña del backoffice |
| `SCRAPER_HEADLESS` | `true` para ejecutar Chromium sin ventana |
| `SCRAPER_IGNORE_HTTPS_ERRORS` | Solo activar si el entorno interno usa certificados no confiables |
| `SCRAPER_NAVIGATION_TIMEOUT_MS` | Tiempo máximo de navegación |
| `SCRAPER_SELECTOR_TIMEOUT_MS` | Tiempo máximo para encontrar controles |
| `SCRAPER_SEARCH_TIMEOUT_MS` | Tiempo máximo para completar el filtro |

La configuración de IIS no está incluida todavía. Se agregará después de validar el flujo contra el backoffice real y aprobar la solución.
