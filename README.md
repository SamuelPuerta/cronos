# CRONOS — Cápsula del Tiempo Digital

Samuel Puerta

CRONOS es una **cápsula del tiempo digital serverless**: un usuario crea un mensaje
dirigido a un destinatario, y ese mensaje se entrega automáticamente **solo si el
usuario deja de hacer "check-in" periódico** (patrón *dead man's switch*). Mientras
el dueño siga confirmando su actividad dentro del intervalo configurado, la cápsula
permanece sellada (`ACTIVE`); si el intervalo vence sin check-in, una tarea
programada la marca como `DELIVERED` y envía el mensaje al destinatario por correo
vía Amazon SES.

Proyecto de laboratorio — Cloud Computing (Serverless Framework + AWS Lambda +
API Gateway + DynamoDB).

## Arquitectura

El sistema está compuesto por:

- **API Gateway (HTTP API)** que expone 7 endpoints REST.
- **8 funciones Lambda** (una por operación, más la automatización programada).
- **DynamoDB** (`CapsulesTable`) como única base de datos, con el GSI
  `StatusNextReviewIndex` para consultas eficientes por estado.
- **EventBridge** que dispara cada 15 minutos la Lambda `reviewExpirations`.
- **Amazon SES** para la entrega del mensaje al destinatario.

El diagrama completo, el diseño de la tabla y las preguntas de reflexión están en
[docs/technical_document.md](docs/technical_document.md).

## Prerrequisitos

- **Node.js 20+** (para Serverless Framework y los plugins)
- **Python 3.13+** (el proyecto usa Python 3.14 como runtime de Lambda y en local)
- **AWS CLI** instalado y configurado (`aws configure` con credenciales válidas)
- **Serverless Framework 4**: `npm install -g serverless`
- **Docker** (opcional, solo para la bonificación de DynamoDB Local)

## Instalación

```bash
# 1. Crear y activar el entorno virtual de Python
python3 -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate

# 2. Instalar dependencias de Python
# Hay dos archivos de requirements:
#   - requirements.txt      -> dependencias de producción (boto3). Es el único
#                              que se empaqueta en el despliegue a Lambda.
#   - requirements-dev.txt  -> incluye requirements.txt + pytest y moto,
#                              necesarios solo para correr los tests en local.
# Para uso normal / despliegue:
pip install -r requirements.txt
# Para desarrollo (si vas a correr los tests unitarios):
pip install -r requirements-dev.txt

# 3. Instalar dependencias de Node (plugins de Serverless)
npm install
```

## Despliegue

```bash
serverless deploy
```

Al finalizar, la salida muestra la URL base de la HTTP API, por ejemplo:

```
endpoint: https://<api-id>.execute-api.us-east-1.amazonaws.com
```

Esa URL es el `<API_URL>` usado en los ejemplos de abajo y el valor de la
variable `base_url` de la colección de Postman (`postman/cronos.postman_collection.json`).

## Pruebas locales con `serverless offline`

```bash
source venv/bin/activate
serverless offline
```

La API queda disponible en `http://localhost:3000`.

> **Importante:** `serverless offline` ejecuta las funciones Lambda en local, pero
> **las operaciones de DynamoDB requieren la tabla real ya desplegada en AWS**
> (es decir, hay que haber corrido `serverless deploy` al menos una vez), o bien
> usar DynamoDB Local como se describe en la siguiente sección. El nombre de la
> tabla se toma de la variable de entorno `CAPSULES_TABLE`, que serverless.yml
> define como `cronos-capsules-<stage>`.

## Testing con DynamoDB Local (opcional / bonificación)

Para probar sin consumir recursos de AWS real:

```bash
# 1. Levantar DynamoDB Local (datos persistentes en volumen Docker)
docker compose up -d

# 2. Crear CapsulesTable (con su GSI) en la instancia local
python scripts/create_local_table.py

# 3. Apuntar los handlers al endpoint local y arrancar la API offline
export DYNAMODB_ENDPOINT_URL=http://localhost:8000
serverless offline

# Para detener conservando los datos:   docker compose down
# Para detener y borrar los datos:      docker compose down -v
```

`src/common/db.py` solo usa el endpoint local si `DYNAMODB_ENDPOINT_URL` está
definida; sin esa variable todo apunta a AWS real.

## Endpoints de la API

| Método | Ruta | Función Lambda | Descripción |
|---|---|---|---|
| POST | `/capsules` | `create` | Crear una cápsula |
| GET | `/capsules` | `list` | Listar cápsulas (query params: `limit`, `lastKey`) |
| GET | `/capsules/{id}` | `get` | Obtener una cápsula por id |
| PUT | `/capsules/{id}` | `update` | Actualizar mensaje, destinatario e intervalo (solo `ACTIVE`) |
| DELETE | `/capsules/{id}` | `remove` | Eliminar una cápsula |
| PATCH | `/capsules/{id}/checkin` | `checkIn` | Registrar check-in (reinicia el temporizador) |
| GET | `/capsules/search?status=ACTIVE` | `search` | Buscar cápsulas por estado vía GSI (Query) |

> **Nota:** la octava función, `reviewExpirations`, **no es un endpoint HTTP**:
> es una Lambda interna programada con EventBridge (`rate(15 minutes)`) que
> revisa cápsulas cuyo `nextReview` ya venció, las marca como `DELIVERED` y
> envía el mensaje por correo con Amazon SES.

### Ejemplos con `curl`

Reemplaza `<API_URL>` por la URL que devuelve el despliegue
(ej. `https://<api-id>.execute-api.us-east-1.amazonaws.com`).

**Crear una cápsula (201):**

```bash
curl -X POST "<API_URL>/capsules" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Si lees esto, olvidé hacer check-in. ¡Saludos del pasado!",
    "recipientEmail": "destinatario@example.com",
    "ownerEmail": "dueno@example.com",
    "checkInIntervalHours": 24
  }'
```

**Crear con payload inválido — provoca un 400:**

```bash
curl -X POST "<API_URL>/capsules" \
  -H "Content-Type: application/json" \
  -d '{"recipientEmail": "destinatario@example.com"}'
# -> {"error": "\"message\" is required and must be text"}
```

**Listar cápsulas (200):**

```bash
curl "<API_URL>/capsules?limit=10"
```

**Obtener una cápsula por id (200):**

```bash
curl "<API_URL>/capsules/<CAPSULE_ID>"
```

**Obtener un id inexistente — provoca un 404:**

```bash
curl "<API_URL>/capsules/non-existent-id"
# -> {"error": "Capsule not found"}
```

**Actualizar una cápsula (200):**

```bash
curl -X PUT "<API_URL>/capsules/<CAPSULE_ID>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Mensaje actualizado",
    "recipientEmail": "nuevo@example.com",
    "ownerEmail": "dueno@example.com",
    "checkInIntervalHours": 48
  }'
```

**Hacer check-in (200):**

```bash
curl -X PATCH "<API_URL>/capsules/<CAPSULE_ID>/checkin"
```

**Buscar cápsulas por estado vía GSI (200):**

```bash
curl "<API_URL>/capsules/search?status=ACTIVE"
# Estados válidos: ACTIVE, DELIVERED, CANCELLED
```

**Eliminar una cápsula (200):**

```bash
curl -X DELETE "<API_URL>/capsules/<CAPSULE_ID>"
```

## Tests unitarios

La suite usa **pytest** con **moto** para simular DynamoDB: no requiere
credenciales reales ni toca recursos de AWS. Requiere haber instalado las
dependencias de desarrollo (`pip install -r requirements-dev.txt`).

```bash
source venv/bin/activate
pytest tests/ -v
```

Incluye tests de validación de payloads y de los handlers (casos de éxito y de
error: 201/200, 400 por payloads o parámetros inválidos, 404 por ids inexistentes
y actualización de `lastCheckIn`/`nextReview` en el check-in).

## Limpieza

Para eliminar **todos** los recursos desplegados en AWS (Lambdas, HTTP API,
tabla DynamoDB y roles IAM):

```bash
serverless remove
```

Si usaste DynamoDB Local:

```bash
docker compose down -v
```
