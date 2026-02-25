# 🚀 Laravel Backend Complete Setup

Herramienta de automatización que levanta un proyecto Laravel completo con Docker y genera todo el backend (modelos, migraciones, controladores, rutas y seeders) a partir de un diagrama de base de datos creado en **MySQL Workbench** (`.mwb`).

---

## 📋 Requisitos previos

Antes de ejecutar el script asegúrate de tener instalado:

| Herramienta | Versión mínima | Verificar con |
|---|---|---|
| Docker | 20+ | `docker --version` |
| Docker Compose | v2 | `docker compose version` |
| Python | 3.8+ | `python3 --version` |
| Git | cualquier | `git --version` |

También necesitas tener en el mismo directorio:

```
backend-repo.zip      ← proyecto Laravel base con docker-compose.yml
laravel_generator.py  ← generador de código
backend_setup.py      ← script principal (este)
tu_modelo.mwb         ← tu diagrama de Workbench
```

---

## ▶️ Cómo ejecutar

```bash
python3 backend_setup.py
```

El script es interactivo y pedirá:

1. **Nombre del proyecto** — se crea una carpeta con ese nombre
2. **Nombre de la base de datos** — si se deja vacío usa el nombre del proyecto
3. **Puerto MySQL** — por default `3307`
4. **Ruta al archivo `.mwb`** — ruta completa o relativa al modelo de Workbench
5. **URL del repositorio Git** — opcional, para hacer push automático

---

## ⚙️ Fases del proceso

```
FASE 1 → Descomprimir y configurar el proyecto Laravel base
FASE 2 → Levantar contenedores Docker (app + db + phpMyAdmin)
FASE 3 → Instalar dependencias Composer, generar APP_KEY y JWT_SECRET
FASE 4 → Parsear el .mwb y generar todo el código backend
FASE 5 → Push al repositorio Git (opcional)
```

Al finalizar el backend queda corriendo con:

| Servicio | URL |
|---|---|
| API Laravel | http://localhost:8000 |
| phpMyAdmin | http://localhost:8080 |
| MySQL | localhost:3307 (o el puerto elegido) |

---

## 📐 Lo que genera automáticamente

Por cada tabla del modelo Workbench se genera:

- **Migración** — con todos los campos, tipos, nullable, defaults y foreign keys usando la sintaxis moderna de Laravel (`foreignId()->constrained()`)
- **Modelo Eloquent** — con `$fillable`, `$casts`, relaciones `belongsTo` y `hasMany` detectadas automáticamente, soporte para `SoftDeletes` si existe columna `deleted_at`
- **Controlador API** — CRUD completo (`index`, `store`, `show`, `update`, `destroy`) con validación de reglas generada por tipo de campo y eager loading de relaciones
- **Seeder** — 10 registros de prueba con datos Faker realistas en español (`es_MX`)
- **Rutas** — `Route::apiResource()` para cada tabla en `routes/api.php`
- **DatabaseSeeder.php** — con todas las llamadas en el **orden correcto de dependencias** para respetar las foreign keys

> Las tablas `users`, `rol` y `estatus` son excluidas de la generación de seeders ya que se asume que tienen sus propios seeders (`RolSeeder`, `EstatusSeeder`, `UserSeeder`) que se llaman primero.

---

## ⚠️ REQUISITOS DEL MODELO EN WORKBENCH

> Esta es la parte más importante. Un modelo mal definido produce migraciones con errores, seeders con datos incorrectos o fallas al ejecutar. Sigue estas reglas al diseñar tu `.mwb`.

### 1. Asigna el tipo correcto a cada columna

**Nunca dejes el tipo en `VARCHAR` si el campo no es texto.** El script intenta corregir algunos casos obvios, pero no puede adivinar todos. Asigna el tipo manualmente en Workbench:

| Si el campo es... | Tipo que debes usar en Workbench |
|---|---|
| Llave primaria entera | `INT` o `BIGINT` con AI (Auto Increment) |
| Llave foránea | `INT` o `BIGINT` (mismo tipo que el PK referenciado) |
| Nombre, apellido, texto corto | `VARCHAR` |
| Descripción larga | `TEXT` |
| Precio, costo, monto | `DECIMAL` |
| Edad, cantidad, número entero | `INT` |
| Fecha (solo día/mes/año) | `DATE` |
| Fecha y hora | `DATETIME` |
| Solo hora | `TIME` |
| Verdadero / Falso | `TINYINT(1)` o `BOOLEAN` |
| Datos JSON | `JSON` |

---

### 2. ⚡ OBLIGATORIO: Define el largo (Length) en VARCHAR

Este es el error más común. Cuando agregas una columna de tipo `VARCHAR` en Workbench, **debes escribir el número de caracteres máximos** en el campo `Length`.

**Cómo hacerlo en Workbench:**

1. Doble clic en la tabla → pestaña **Columns**
2. En la columna `Datatype` escribe `VARCHAR(100)` directamente, o bien
3. Escribe `VARCHAR` en Datatype y luego `100` en el campo **Length** a la derecha

```
✅ CORRECTO                    ❌ INCORRECTO
VARCHAR(100)  → nombres        VARCHAR  → nombres (sin largo)
VARCHAR(255)  → descripcion    VARCHAR  → descripcion
VARCHAR(20)   → telefono       VARCHAR  → telefono
```

Si dejas `VARCHAR` sin largo, el script asigna `255` por default, lo que puede generar migraciones más pesadas de lo necesario o reglas de validación incorrectas.

**Largos recomendados según el tipo de dato:**

| Campo típico | Largo sugerido |
|---|---|
| Nombre, apellido | `100` |
| Email | `150` |
| Teléfono | `20` |
| Dirección | `255` |
| Ciudad, estado | `100` |
| Código postal | `10` |
| Título | `200` |
| Descripción corta | `255` |
| Contraseña (hash) | `255` |
| UUID | `36` |
| Token | `64` o `255` |
| URL | `500` |
| Especialidad, cargo | `150` |

---

### 3. Define precisión y escala en DECIMAL

Para campos de tipo `DECIMAL` (precios, montos, coordenadas) debes definir:

- **Precision** — total de dígitos (enteros + decimales)
- **Scale** — cuántos de esos dígitos son decimales

```
DECIMAL(10, 2) → hasta 99,999,999.99  ← precios normales
DECIMAL(8, 2)  → hasta 999,999.99     ← precios menores
DECIMAL(5, 2)  → hasta 999.99         ← porcentajes
DECIMAL(10, 6) → hasta 9999.999999    ← coordenadas GPS
```

**En Workbench:** columna `Datatype` escribe `DECIMAL(10,2)` directamente.

Si no defines precisión/escala, el script usa `DECIMAL(8,2)` por default.

---

### 4. Marca correctamente NOT NULL vs NULL

En Workbench la columna `NN` (Not Null) de la pestaña Columns determina si el campo es obligatorio:

- ✅ **Marcado (NN)** → campo obligatorio → `required` en validación → sin `->nullable()` en migración
- ☐ **Desmarcado** → campo opcional → `nullable` en validación → `->nullable()` en migración

Marca como `NN` solo los campos que realmente son requeridos en tu negocio.

---

### 5. Define bien las Foreign Keys

Para que las relaciones entre tablas se generen correctamente:

1. La columna FK debe ser del **mismo tipo y tamaño** que el PK al que apunta
   - Si `usuarios.id` es `BIGINT`, entonces `pedidos.usuario_id` también debe ser `BIGINT`
2. Dibuja la relación en el diagrama (línea entre tablas) — no solo pongas la columna
3. Nombra las FK con el patrón `tabla_referenciada_id` para que el script las detecte automáticamente
   - ✅ `medico_id`, `cliente_id`, `servicio_id`
   - ❌ `id_medico`, `medID`, `fk1`

---

### 6. Columnas especiales reconocidas automáticamente

El script detecta y maneja de forma especial:

| Columna | Comportamiento |
|---|---|
| `id` (INT/BIGINT AI) | Se genera como `$table->id()` |
| `created_at`, `updated_at` | Se omiten — Laravel los maneja con `$table->timestamps()` |
| `deleted_at` | Activa `SoftDeletes` en el modelo y `$table->softDeletes()` |
| Columna terminada en `_id` | Se trata como FK automáticamente |
| Columna `email` o que contenga "email" | Se agrega `->unique()` en la migración |

---

### 7. Ejemplo de modelo bien definido

```
┌─────────────────────────────────┐
│ medicos                         │
├──────────────┬──────────┬───────┤
│ id           │ BIGINT   │ AI NN │
│ nombre       │ VARCHAR  │ 100 NN│
│ apellido_pat │ VARCHAR  │ 100 NN│
│ apellido_mat │ VARCHAR  │ 100   │
│ especialidad │ VARCHAR  │ 150 NN│
│ email        │ VARCHAR  │ 150 NN│
│ telefono     │ VARCHAR  │ 20    │
│ created_at   │ DATETIME │       │
│ updated_at   │ DATETIME │       │
└──────────────┴──────────┴───────┘

┌──────────────────────────────────────┐
│ citas                                │
├───────────────┬──────────┬───────────┤
│ id            │ BIGINT   │ AI NN     │
│ medico_id     │ BIGINT   │ NN (FK→medicos.id) │
│ cliente_id    │ BIGINT   │ NN (FK→clientes.id)│
│ fecha_cita    │ DATE     │ NN        │
│ hora_inicio   │ TIME     │ NN        │
│ hora_fin      │ TIME     │ NN        │
│ motivo        │ VARCHAR  │ 255       │
│ costo         │ DECIMAL  │ (10,2) NN │
│ created_at    │ DATETIME │           │
│ updated_at    │ DATETIME │           │
└───────────────┴──────────┴───────────┘
```

---

## 🌱 Seeders generados

Cada tabla (excepto `users`, `rol`, `estatus`) recibe un seeder con **10 registros de prueba** usando Faker en español (`es_MX`). El generador detecta el tipo de dato esperado por el nombre de la columna:

| Nombre de columna contiene... | Dato generado |
|---|---|
| `nombre`, `nombres` | Nombre de pila real |
| `apellido`, `apellido_paterno`, `apellido_materno` | Apellido real |
| `email`, `correo` | Email único válido |
| `telefono`, `celular` | Número telefónico |
| `especialidad`, `cargo`, `puesto` | Título de trabajo real |
| `precio`, `costo`, `monto`, `total` | Número decimal (10.00 – 9999.99) |
| `fecha_*`, `*_date` | Fecha en formato `Y-m-d` |
| `hora_*`, `*_time` | Hora en formato `H:i:s` |
| `direccion`, `domicilio` | Dirección de calle |
| `descripcion`, `detalle`, `notas` | Oración coherente |
| Columna FK (`*_id`) | ID aleatorio de la tabla referenciada |
| `VARCHAR` sin coincidencia | Palabras reales (1–3 según largo) |

El `DatabaseSeeder.php` llama a todos los seeders en el orden topológico correcto, garantizando que las tablas padre existan antes de insertar datos en las tablas hijo.

---

## 🐛 Errores comunes y soluciones

### Las migraciones fallan con "Column not found" o "Unknown column"
**Causa:** Una FK apunta a una tabla que aún no existe.
**Solución:** Verifica que las relaciones estén bien dibujadas en Workbench. El script ordena las migraciones automáticamente, pero necesita que las foreign keys estén definidas en el diagrama (no solo las columnas `_id`).

### Los seeders fallan con "SQLSTATE: foreign key constraint fails"
**Causa:** Se intenta insertar un registro con un `_id` que no existe en la tabla padre.
**Solución:** Corre los seeders en orden: primero las tablas sin dependencias. El `DatabaseSeeder.php` generado ya maneja esto, pero si corres seeders manualmente asegúrate del orden.

### Los seeders fallan con "Class not found"
**Causa:** El seeder fue copiado pero Composer no lo conoce.
**Solución:** Ejecuta dentro del contenedor:
```bash
docker exec <container_app> composer dump-autoload
```

### Los tipos de columna salen como `string` cuando deberían ser `integer` o `decimal`
**Causa:** En Workbench la columna tiene tipo `VARCHAR` en lugar del tipo correcto.
**Solución:** Corrige el tipo en Workbench y regenera. Revisa la sección [Asigna el tipo correcto](#1-asigna-el-tipo-correcto-a-cada-columna).

### Re-ejecutar solo los seeders sin borrar las tablas
```bash
docker exec <container_app> php artisan db:seed --force
```

### Re-ejecutar migraciones y seeders desde cero
```bash
docker exec <container_app> php artisan migrate:fresh --seed
```

---

## 📝 Comandos útiles

```bash
# Ver logs en tiempo real
docker compose -p <proyecto> logs -f

# Entrar al contenedor de la app
docker compose -p <proyecto> exec app bash

# Detener contenedores
docker compose -p <proyecto> down

# Reiniciar contenedores
docker compose -p <proyecto> restart

# Ver estado de los contenedores
docker compose -p <proyecto> ps
```

---

## 📁 Estructura generada

```
<proyecto>/
├── app/
│   ├── Http/
│   │   └── Controllers/
│   │       └── Api/
│   │           ├── ClienteController.php   ← CRUD completo
│   │           ├── MedicoController.php
│   │           └── ...
│   └── Models/
│       ├── Cliente.php                     ← con relaciones
│       ├── Medico.php
│       └── ...
├── database/
│   ├── migrations/
│   │   ├── ..._create_medicos_table.php    ← ordenadas por FK
│   │   ├── ..._create_clientes_table.php
│   │   └── ...
│   └── seeders/
│       ├── DatabaseSeeder.php              ← orden correcto de FK
│       ├── MedicoSeeder.php                ← 10 registros Faker
│       ├── ClienteSeeder.php
│       └── ...
└── routes/
    └── api.php                             ← apiResource por tabla
```
