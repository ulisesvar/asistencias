# Asistencia — bot de Telegram con verificación por geolocalización

Bot de Telegram para tomar asistencia en clase. Cada alumno se registra con su número de
cuenta y su usuario de Telegram. Cuando el profesor abre el pase de lista, el bot pide a
los alumnos registrados que envíen su ubicación; si están dentro de un radio configurable
(por defecto 50 m) del salón de clases, la asistencia se registra en PostgreSQL.

## Cómo funciona

1. El alumno le escribe `/start` al bot y registra su número de c   uenta.
2. El profesor (uno de los IDs listados en `TEACHER_IDS`) ejecuta `/pase [minutos]` en un
   chat privado con el bot. Esto abre una sesión de asistencia y notifica por mensaje
   directo a todos los alumnos registrados.
3. Cada alumno comparte su ubicación actual en el chat con el bot (Telegram: clip 📎 →
   Ubicación).
4. Si la distancia al salón es menor o igual a `CLASSROOM_RADIUS_METERS`, se registra la
   asistencia. Un alumno solo puede registrar una asistencia por sesión.
5. El profesor puede consultar `/estado` para ver cuántos han asistido, y `/cerrar` para
   cerrar el pase de lista antes de que expire el tiempo.
6. Ante un reclamo ("mi ubicación salió mal", "no me dejó pasar asistencia"), el profesor
   puede usar `/historial [numero de cuenta]` para ver los últimos intentos de ese alumno
   (éxitos y fallos), con fecha, resultado, coordenadas, distancia al salón y precisión GPS
   reportada por Telegram.

El bot opera por **long polling**: se conecta hacia afuera a la API de Telegram y no
necesita ningún puerto expuesto ni HTTPS/reverse proxy.

## Variables de entorno

Todas las variables sensibles y de configuración se reciben por entorno, nunca están
hardcodeadas ni se incluyen en el repositorio o la imagen. Ver [`.env.example`](.env.example).

| Variable | Obligatoria | Descripción |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | sí | Token del bot, obtenido de [@BotFather](https://t.me/BotFather) |
| `TEACHER_IDS` | sí | IDs numéricos de Telegram de los profesores, separados por comas |
| `CLASSROOM_LAT` | sí | Latitud del salón de clases |
| `CLASSROOM_LON` | sí | Longitud del salón de clases |
| `CLASSROOM_RADIUS_METERS` | no (default `50`) | Radio de tolerancia en metros |
| `SESSION_DEFAULT_MINUTES` | no (default `10`) | Duración por defecto del pase de lista |
| `DATABASE_URL` | sí | Cadena de conexión a PostgreSQL |
| `LOG_LEVEL` | no (default `INFO`) | Nivel de logging |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | sí (usadas por el contenedor de PostgreSQL en `docker-compose.yml`) | Credenciales de la base de datos |

Para saber tu ID numérico de Telegram (para `TEACHER_IDS`), escríbele a
[@userinfobot](https://t.me/userinfobot).

## Desarrollo local

Requiere Docker y Docker Compose.

```bash
cp .env.example .env
# edita .env con tus valores reales

docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

`docker-compose.dev.yml` agrega la instrucción `build:` para compilar la imagen
localmente. El `docker-compose.yml` base **no** tiene `build:` — solo referencia la
imagen publicada en GHCR, tal como se usa en producción.

## Despliegue en producción

El servidor de producción **no construye la imagen**. Solo hace pull de la imagen ya
publicada en GitHub Container Registry y la levanta:

```bash
cp .env.example .env
# edita .env con los valores reales de producción

docker compose pull
docker compose up -d
```

Esto trae `bot` (este proyecto) y `db` (PostgreSQL 16), con:

- **Arranque automático**: el contenedor `bot` corre `python -m bot.main` como `CMD`, sin
  comandos manuales adicionales.
- **Sin privileged / sin socket de Docker**: ningún servicio requiere `privileged: true`
  ni montar `/var/run/docker.sock`.
- **Puertos**: ninguno se expone. El bot es 100% saliente (long polling) y PostgreSQL
  solo es alcanzable dentro de la red interna de docker-compose.
- **Volumen persistente**: `pgdata`, para los datos de PostgreSQL (alumnos, sesiones,
  asistencias). El bot en sí es stateless.
- **Healthcheck**: `bot` expone un heartbeat interno verificado con
  `python -m bot.healthcheck`; `db` usa `pg_isready`.
- **Logs**: toda la salida va a stdout/stderr (accesible con `docker compose logs -f`).

Para actualizar a una versión específica en vez de `latest`:

```bash
IMAGE_TAG=1.2.0 docker compose pull
IMAGE_TAG=1.2.0 docker compose up -d
```

(o define `IMAGE_TAG=1.2.0` directamente en tu `.env`).

## Publicación de la imagen (CI/CD)

[`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml) construye
y publica automáticamente la imagen en `ghcr.io/ulisesvar/asistencias`:

- En cada push a `main`: publica el tag `latest` (además de un tag `sha-<commit corto>`
  para trazabilidad).
- En cada tag `vX.Y.Z` (ej. `git tag v1.2.0 && git push origin v1.2.0`): publica los tags
  de versión `X.Y.Z` y `X.Y`, además de actualizar `latest`.
- La imagen se construye únicamente para `linux/amd64`.
- Usa `GITHUB_TOKEN` (permiso `packages: write`, ya incluido en el workflow) — no se
  necesita ningún secreto adicional.

No es necesario ejecutar Docker Buildx ni publicar manualmente: basta con hacer push a
`main` o crear un tag de versión.

## Base de datos

El esquema (`db/schema.sql`) se aplica automáticamente la primera vez que arranca el
contenedor de PostgreSQL, vía `/docker-entrypoint-initdb.d`. Tablas:

- `students`: alumnos registrados (cuenta, usuario y ID de Telegram).
- `attendance_sessions`: cada pase de lista abierto por un profesor.
- `attendances`: asistencias exitosas, con distancia calculada al salón.
- `attendance_attempts`: **todo** intento de envío de ubicación, exitoso o no (no
  registrado, sin pase abierto, pase ya cerrado, ya había asistido, fuera de rango),
  con coordenadas, distancia y precisión GPS reportada. Sirve como bitácora para resolver
  reclamos de alumnos sobre su ubicación. Consultable con `/historial [numero de cuenta]`.

Si ya tienes un despliegue existente (la base de datos ya fue inicializada antes), el
esquema en `db/schema.sql` **no** se vuelve a aplicar automáticamente — `docker-entrypoint-
initdb.d` solo corre en un volumen `pgdata` nuevo. Para agregar la tabla nueva a una base
ya existente, aplica manualmente el bloque de `attendance_attempts` de `db/schema.sql`,
por ejemplo:

```bash
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < db/schema.sql
```

(es seguro reejecutar todo el archivo: todas las sentencias usan `IF NOT EXISTS`).

## Seguridad

- Ningún token, contraseña ni `.env` está incluido en el repositorio ni en la imagen
  (ver [`.gitignore`](.gitignore) y [`.dockerignore`](.dockerignore)).
- El contenedor de la aplicación corre con un usuario sin privilegios (no root).
- La autorización de comandos administrativos (`/pase`, `/cerrar`, `/estado`) se valida
  contra `TEACHER_IDS` en cada solicitud.
