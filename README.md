# Asistencia — bot de Telegram con verificación por geolocalización

Bot de Telegram para tomar asistencia en clase. Cada alumno se registra con su número de
cuenta y su usuario de Telegram. Cuando el profesor abre el pase de lista, el bot pide a
los alumnos registrados que envíen su ubicación; si están dentro de un radio configurable
(por defecto 50 m) del salón de clases, la asistencia se registra en PostgreSQL.

## Cómo funciona

1. El alumno le escribe `/start` al bot y registra su número de cuenta.
2. El profesor (uno de los IDs listados en `TEACHER_IDS`) ejecuta `/pase [minutos]` en un
   chat privado con el bot. Esto abre una sesión de asistencia y notifica por mensaje
   directo a todos los alumnos registrados.
3. Cada alumno comparte su ubicación actual en el chat con el bot (Telegram: clip 📎 →
   Ubicación).
4. Si la distancia al salón es menor o igual a `CLASSROOM_RADIUS_METERS`, se registra la
   asistencia. Un alumno solo puede registrar una asistencia por sesión.
5. El profesor puede consultar `/estado` para ver cuántos han asistido, y `/cerrar` para
   cerrar el pase de lista antes de que expire el tiempo.

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
- `attendances`: asistencias registradas, con distancia calculada al salón.

## Consulta de calificaciones (`/calif`)

Cualquier alumno registrado puede escribir `/calif` (sin argumentos) en un chat privado con el
bot y recibe su **calificación actual** (no necesariamente la final): el promedio, peso y
aportación de cada categoría y el detalle por actividad (`Tarea 1`, `Examen 1`, `A/P`; una
actividad sin evaluar aparece como `Pendiente`, un cero real como `0 / 100`).

- El bot **no calcula** calificaciones: pide el resultado a la plataforma académica
  (`GET /bot/evaluation/{numero_de_cuenta}`) y solo lo presenta.
- La cuenta se toma **únicamente** del registro del alumno (`students.telegram_id` →
  `students.account_number`); cualquier texto después de `/calif` se ignora, así que un alumno
  no puede consultar a otro. Un alumno no registrado recibe un aviso y no se llama a la plataforma.
- Solo funciona en chat privado (en grupos el bot pide usar el privado).
- Solo lectura: no hay migraciones ni cambios en la base de datos del bot.

Variables de entorno (en `.env`, junto a las demás):

| Variable | Descripción |
|---|---|
| `ACADEMIC_API_BASE_URL` | URL base de la plataforma académica, p. ej. `https://api.canumpe.com` |
| `ACADEMIC_API_KEY` | Llave de servidor con rol `bot` (restringida a un curso). **Nunca** al repositorio ni a los logs. |
| `ACADEMIC_API_TIMEOUT_SECONDS` | Opcional, por defecto `10` |

Si falta alguna de las dos primeras, `/calif` responde que la consulta no está disponible y
el resto del bot (asistencia) funciona normalmente.

## Pruebas

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Las pruebas no llaman a ningún servicio real ni a la base de datos (la plataforma académica se
simula con `httpx.MockTransport`).

## Seguridad

- Ningún token, contraseña ni `.env` está incluido en el repositorio ni en la imagen
  (ver [`.gitignore`](.gitignore) y [`.dockerignore`](.dockerignore)).
- El contenedor de la aplicación corre con un usuario sin privilegios (no root).
- La autorización de comandos administrativos (`/pase`, `/cerrar`, `/estado`) se valida
  contra `TEACHER_IDS` en cada solicitud.
