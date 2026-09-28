# Guia paso a paso para desplegar UKIP en Dokploy

Esta guia cubre el despliegue de UKIP en un VPS administrado con Dokploy para
validaciones reales con stakeholders de ciencia y tecnologia.

## Objetivo del despliegue

Usaremos dos dominios:

- Frontend: `https://ukip.inbounduxd.com`
- Backend API: `https://api.ukip.inbounduxd.com`

Y tres servicios principales:

- `ukip-frontend`: Next.js, puerto interno `3004`
- `ukip-backend`: FastAPI, puerto interno `8000`
- PostgreSQL: gestionado por Dokploy

## 1. Preparar DNS

En el proveedor DNS de `inbounduxd.com`, crea o verifica estos registros:

```text
ukip.inbounduxd.com      A      <IP_DEL_VPS>
api.ukip.inbounduxd.com  A      <IP_DEL_VPS>
```

Si usas Cloudflare, deja ambos registros en modo DNS only durante la primera
validacion. Luego puedes activar proxy si ya verificaste TLS, CORS y websockets.

## 2. Preparar GitHub Actions

El frontend embebe `NEXT_PUBLIC_API_URL` durante el build. Antes de generar la
imagen que usara Dokploy, configura esta variable en GitHub:

```env
NEXT_PUBLIC_API_URL=https://api.ukip.inbounduxd.com
```

Ruta sugerida:

1. Abre el repositorio en GitHub.
2. Ve a `Settings`.
3. Entra a `Secrets and variables`.
4. Abre `Actions`.
5. En la pestana `Variables`, crea:
   - nombre: `NEXT_PUBLIC_API_URL`
   - valor: `https://api.ukip.inbounduxd.com`

Despues de guardar esa variable, dispara un nuevo build de Docker desde `main`
para que la imagen del frontend quede construida con el dominio correcto.

## 3. Preparar acceso a GHCR

Los paquetes de GHCR pueden estar privados. Si Dokploy no puede hacer pull de
las imagenes, crea un token de GitHub con permiso:

```text
read:packages
```

En Dokploy configura credenciales para:

```text
Registry: ghcr.io
Username: <usuario_github_con_acceso>
Password: <github_token_read_packages>
```

Usaremos estas imagenes como referencia:

```env
UKIP_BACKEND_IMAGE=ghcr.io/keilynrp/ukip-backend:sha-6b7835e
UKIP_FRONTEND_IMAGE=ghcr.io/keilynrp/ukip-frontend:sha-6b7835e
```

Si generas un build mas reciente, usa el nuevo tag `sha-<short_sha>` publicado
por GitHub Actions.

## 4. Crear PostgreSQL en Dokploy

En Dokploy:

1. Crea un nuevo proyecto o usa el proyecto de UKIP.
2. Crea un servicio de base de datos PostgreSQL.
3. Usa una version moderna, idealmente PostgreSQL 16.
4. Activa almacenamiento persistente.
5. Activa backups automaticos.
6. Copia el connection string interno que entrega Dokploy.

El valor debe quedar con esta forma:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/DB_NAME
```

Guarda ese valor solo en Dokploy. No lo pongas en Git.

## 5. Crear la aplicacion Compose de UKIP

En Dokploy:

1. Crea un nuevo servicio tipo Docker Compose.
2. Conectalo al repositorio `keilynrp/universal-knowledge-intelligence-platform`.
3. Selecciona la rama `main`.
4. Usa como compose file:

```text
docker-compose.prod.yml
```

5. Asegura que el servicio tenga acceso a las credenciales GHCR si las imagenes
   siguen privadas.

## 6. Cargar variables de entorno

En la seccion de variables de Dokploy para la app Compose, carga:

```env
UKIP_BACKEND_IMAGE=ghcr.io/keilynrp/ukip-backend:sha-6b7835e
UKIP_FRONTEND_IMAGE=ghcr.io/keilynrp/ukip-frontend:sha-6b7835e

DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/DB_NAME
RUN_DB_MIGRATIONS_ON_START=0

ADMIN_USERNAME=superadmin
ADMIN_PASSWORD=<PASSWORD_SEGURO>
ADMIN_PASSWORD_HASH=

JWT_SECRET_KEY=<SECRETO_LARGO>
SESSION_SECRET_KEY=<SECRETO_LARGO>
ENCRYPTION_KEY=<FERNET_KEY>

ALLOWED_ORIGINS=https://ukip.inbounduxd.com
NEXT_PUBLIC_API_URL=https://api.ukip.inbounduxd.com

LOG_LEVEL=INFO
LOG_FORMAT=json

SENTRY_ENABLED=0
SENTRY_ENABLE_TRACING=0
SENTRY_TRACES_SAMPLE_RATE=0.0
SENTRY_SEND_DEFAULT_PII=0

SCHOLAR_USE_FREE_PROXIES=0
UKIP_ENABLE_LLM_QUERY_REFORMULATION=0
```

Genera `ENCRYPTION_KEY` localmente con:

```powershell
.\.venv\Scripts\python.exe scripts\generate_fernet_key.py
```

Para `JWT_SECRET_KEY` y `SESSION_SECRET_KEY`, usa un generador seguro o tu
password manager.

## 7. Configurar dominios en Dokploy

En la app Compose de UKIP, abre la seccion de dominios.

Configura:

```text
Dominio:  ukip.inbounduxd.com
Servicio: ukip-frontend
Puerto:   3004
HTTPS:    enabled
```

Y:

```text
Dominio:  api.ukip.inbounduxd.com
Servicio: ukip-backend
Puerto:   8000
HTTPS:    enabled
```

Despues de cambios de dominio, redeploya la aplicacion Compose para que Dokploy
regenere la configuracion de Traefik.

### 7.1 IP real del cliente detras de Cloudflare (#413)

Cloudflare esta delante del origen, asi que Traefik recibe cada peticion desde
una IP de Cloudflare. Por defecto Traefik descarta el `X-Forwarded-For` que
manda Cloudflare y lo sustituye por esa IP, y el backend nunca ve al cliente:
el audit log, el log de peticiones y los rate limits quedan atados al proxy.

1. En Dokploy, abre la configuracion de Traefik (`traefik.yml`) y agrega a cada
   entry point publico (normalmente `web` y `websecure`) el bloque
   `forwardedHeaders` de [`deploy/traefik/forwarded-headers.yml`](../../deploy/traefik/forwarded-headers.yml).
   Solo rangos de Cloudflare: nunca redes internas.
2. Reinicia Traefik.
3. Verifica desde tu propia conexion: abre la pagina del **Audit Log** en UKIP
   (leer el audit log queda auditado, #375; el login no, porque `/auth/` no se
   audita) y luego, en la terminal de **ukip-backend** (una sola linea):

   ```bash
   python -c "import backend.database as d; from sqlalchemy import text; c=d.SessionLocal(); print(c.execute(text(\"SELECT ip_address FROM audit_logs ORDER BY id DESC LIMIT 3\")).all()); c.close()"
   ```

   Tiene que aparecer tu IP publica (la que muestra, por ejemplo,
   `https://ifconfig.me`), no una `10.x`, `172.x` ni una de Cloudflare.

El backend ya confia en esos saltos por si solo: `docker/trusted-proxies.txt`
lista las redes internas y los rangos de Cloudflare, y el entrypoint se la pasa
a uvicorn. Si Cloudflare publica rangos nuevos, actualiza ese archivo y
`deploy/traefik/forwarded-headers.yml` juntos (un test exige que coincidan).

## 8. Ejecutar migracion inicial

Antes de abrir trafico a usuarios, ejecuta una vez:

```bash
alembic upgrade head
```

Debe correr usando la imagen backend y las mismas variables de produccion,
especialmente `DATABASE_URL`.

Opciones practicas:

- usar una consola del servicio backend en Dokploy
- ejecutar un one-off command con la imagen backend
- activar temporalmente el servicio `ukip-migrate` del compose si Dokploy lo
  permite en tu flujo

Cuando termine correctamente, deja `RUN_DB_MIGRATIONS_ON_START=0`.

## 9. Primer deploy

Secuencia recomendada:

1. Despliega PostgreSQL.
2. Verifica que PostgreSQL este healthy.
3. Ejecuta `alembic upgrade head`.
4. Despliega `ukip-backend`.
5. Verifica `https://api.ukip.inbounduxd.com/health`.
6. Despliega `ukip-frontend`.
7. Verifica `https://ukip.inbounduxd.com`.

Resultado esperado:

```text
https://api.ukip.inbounduxd.com/health -> 200
https://ukip.inbounduxd.com -> UI cargada
```

## 10. Smoke test funcional

Haz esta validacion antes de invitar stakeholders:

1. Entrar con `superadmin`.
2. Abrir Home.
3. Importar un archivo pequeno de ciencia o tecnologia.
4. Confirmar que se crea `import_batch`.
5. Abrir catalogo interno.
6. Enriquecer un registro.
7. Abrir Executive Dashboard.
8. Crear un Report/Brief.
9. Crear un Portal de catalogo desde esa ingesta.
10. Abrir el portal autenticado.
11. Si el portal es publico, probarlo en ventana privada.

## 11. Backups y rollback

Antes de la primera sesion con stakeholders:

1. Confirma que existe al menos un backup de PostgreSQL.
2. Prueba restaurar en un entorno separado si Dokploy lo permite.
3. Anota los tags de imagen anteriores.

Rollback basico:

```env
UKIP_BACKEND_IMAGE=ghcr.io/keilynrp/ukip-backend:sha-<sha_anterior>
UKIP_FRONTEND_IMAGE=ghcr.io/keilynrp/ukip-frontend:sha-<sha_anterior>
```

Luego redeploya la app Compose.

Si el problema es de schema o datos, detente antes de redeployar y restaura el
backup de PostgreSQL adecuado.

## 12. Guardrails para este piloto

Mantener durante la primera validacion:

- una sola replica de backend
- paquetes GHCR pinneados por SHA, no `latest`
- `ALLOWED_ORIGINS` restringido a `https://ukip.inbounduxd.com`
- backups activos
- trazas de Sentry apagadas inicialmente
- sin multiples replicas hasta separar schedulers/background jobs

## 13. Checklist final

Antes de compartir la URL:

- DNS resuelve al VPS
- TLS activo para ambas URLs
- backend health en `200`
- frontend carga sin errores CORS
- login funciona
- import funciona
- portal desde ingesta funciona
- report/brief funciona
- backup confirmado
- rollback tag identificado

## Referencias internas

- [D:\universal-knowledge-intelligence-platform\docker-compose.prod.yml](D:\universal-knowledge-intelligence-platform\docker-compose.prod.yml)
- [D:\universal-knowledge-intelligence-platform\.env.dokploy.example](D:\universal-knowledge-intelligence-platform\.env.dokploy.example)
- [D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_VPS_RUNBOOK.md](D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_VPS_RUNBOOK.md)
- [D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_PILOT_DEPLOYMENT_VALUES.md](D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_PILOT_DEPLOYMENT_VALUES.md)
