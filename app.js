---
name: Auditoría y Saneamiento de VPS y WordPress
description: Guía táctica para gestión, diagnóstico y mantenimiento del VPS 212.85.2.21 (Coolify + Traefik + Docker). Incluye arquitectura de bots Flask, WordPress, n8n, swap y DNS.
---

# Habilidad: Arquitectura e Infraestructura del VPS (212.85.2.21)

## Arquitectura actual (Junio 2026)

| Item | Valor |
|---|---|
| OS | Ubuntu 22.04.5 LTS |
| IP | `212.85.2.21` (VPS nuevo) |
| IP vieja | `181.215.135.56` (servidor anterior — no usar) |
| RAM | 7.8 GB |
| Disco | 100 GB / ~36 GB usados |
| Swap | 2 GB (`/swap`) + 4 GB extra (`/swapfile2`) = **6 GB total** |
| Panel de deploy | **Coolify** — `http://212.85.2.21:8000` |
| Proxy inverso | **Traefik** (gestionado por Coolify) — toma puertos 80 y 443 |
| SSL | Let's Encrypt automático vía Traefik |
| DNS | **Cloudflare** (proxy naranja activo en todos los dominios) |
| Docker | 29.1.3 — todos los servicios corren en contenedores |
| Coolify API token | `2|SaDqAwlbcafTP5Aj0ToTrWYa71USUM0DrbiDdWMi52a15165` |

> **IMPORTANTE:** El VPS anterior (`181.215.135.56`) tenía CyberPanel + OpenLiteSpeed + Nginx. Ya no se usa. Si un dominio sigue respondiendo con errores o a la IP vieja, verificar el registro A en Cloudflare.

---

## Servicios desplegados en Coolify

### Bots Flask (Python)

Todos los bots están en `e:\Proyectos\Chatbots\` y se despliegan desde sus repositorios GitHub vía Coolify.

| Bot | UUID Coolify | Dominio | Tipo |
|---|---|---|---|
| `geniabot` | `w12idmq96t1fhomlxyplgmee` | `geniabot.tuexitoprofesional.com.ar` | Frontend + API (ChromaDB) |
| `lexelbot` | `oz9pnhy34h50m3daty44zwur` | `lexelbot.tuexitoprofesional.com.ar` | Frontend + API |
| `databot` | — | `databot.tuexitoprofesional.com.ar` | Frontend + API |
| `pamibot` | — | `pamibot.tuexitoprofesional.com.ar` | Frontend + API |
| `cipbabot` | `x8wjil3bei03thrpskdbymnf` | `cipba.tuexitoprofesional.com.ar` | Frontend + API |
| `futurekids` | `g8cbeetk9i345r51yszjpkmh` | `futurekids.tuexitoprofesional.com.ar` | **API pura** (plugin Moodle, sin frontend) |

### WordPress

| Sitio | Puerto interno | Dominio |
|---|---|---|
| `ia.tuexitoprofesional.com.ar` | `8086` | WP con acceso al chatbot |
| `pythonyn8n.tuexitoprofesional.com.ar` | `8085` | WP con n8n integrado |

### Otros servicios

| Servicio | Dominio |
|---|---|
| n8n | `n8n.graduadosfiuba.org` |
| Coolify panel | `http://212.85.2.21:8000` (no expuesto públicamente) |

---

## Arquitectura de Bots Flask

### Estructura del repositorio (patrón estándar)
```
botname/
├── Dockerfile
├── api/
│   ├── api.py        ← app Flask principal
│   ├── wsgi.py       ← entry point: `from api import app`
│   ├── bot.py
│   ├── requirements.txt
│   └── ...
└── frontend/         ← HTML/JS/CSS servido por Flask (si aplica)
```

### Configuración crítica de Flask-Talisman

**Todos los bots detrás de Traefik DEBEN tener `force_https=False`:**
```python
from flask_talisman import Talisman
talisman = Talisman(app, force_https=False, content_security_policy=None)
```

Sin `force_https=False`, Talisman redirige HTTP→HTTPS dentro del contenedor, lo que causa bucle infinito de redirección o 404 porque Traefik ya termina el SSL externamente.

### Servir frontend desde Flask
```python
import os
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')

@app.route('/', defaults={'path': 'index.html'})
@app.route('/<path:path>')
def serve_frontend(path):
    return send_from_directory(FRONTEND_DIR, path)
```

El directorio `frontend/` debe existir **un nivel arriba de `api/`**, es decir en la raíz del repo.

### Dockerfile estándar para bots con frontend
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir gunicorn -r api/requirements.txt

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", \
     "--threads", "4", "--worker-class", "gthread", "--timeout", "60", \
     "--chdir", "api", "wsgi:app"]
```

> Si el bot tiene `frontend/`, el `COPY . .` lo incluye automáticamente. No hace falta un `COPY frontend/` explícito cuando se usa `COPY . .`.

---

## Gestión de Swap — CRÍTICO para builds

### Problema
Bots con dependencias pesadas (`chromadb`, `onnxruntime`, `tiktoken`) fallan el build con **exit code 255** (OOM killer) cuando la RAM disponible es baja.

### Estado actual
- `/swap` — 2 GB (swap original del sistema)
- `/swapfile2` — 4 GB (agregado para builds, **persistente en `/etc/fstab`**)
- **Total: 6 GB de swap**

### Si un build falla con exit code 255
```bash
# 1. Verificar RAM y swap
free -h

# 2. Limpiar cache de Docker para liberar RAM
docker image prune -af
docker builder prune -af

# 3. Liberar swap usado (resetear)
swapoff -a && swapon -a

# 4. Si sigue sin alcanzar, agregar más swap
fallocate -l 4G /swapfile2
chmod 600 /swapfile2
mkswap /swapfile2
swapon /swapfile2
echo '/swapfile2 none swap sw 0 0' >> /etc/fstab
```

---

## Coolify — Operaciones comunes

### Disparar redeploy vía API
```python
import requests
API = "http://212.85.2.21:8000/api/v1"
HEADERS = {"Authorization": "Bearer 2|SaDqAwlbcafTP5Aj0ToTrWYa71USUM0DrbiDdWMi52a15165"}

r = requests.get(f"{API}/deploy?uuid=<UUID_APP>&force=true", headers=HEADERS)
print(r.json())
```

> Usar **GET** (no POST) para el endpoint `/deploy` de esta versión de Coolify.

### Listar aplicaciones
```python
r = requests.get(f"{API}/applications", headers=HEADERS)
for app in r.json():
    print(app['uuid'], app['name'])
```

### Verificar contenido de un container
```bash
docker exec <container_name> ls /app/
docker exec <container_name> cat /app/api/api.py
```

### Encontrar nombre de container por UUID de Coolify
```bash
docker ps --format '{{.Names}}' | grep <primeros_chars_uuid>
```

---

## DNS y Cloudflare

- Todos los dominios usan Cloudflare como proxy (nube naranja).
- Cloudflare termina SSL y reenvía HTTP a Traefik en el VPS.
- Traefik recibe en puerto 80, y gestiona sus propios certificados para HTTPS interno.
- **Si un dominio no responde:** verificar que el registro A apunte a `212.85.2.21` (no a `181.215.135.56`).

### Verificar DNS desde el VPS
```bash
dig +short <dominio>
# Debe devolver 212.85.2.21 o una IP de Cloudflare
```

### Verificar estado HTTP de todos los bots
```python
import paramiko
HOST = "212.85.2.21"; USER = "root"; PASS = "Graduados/2024"
def run(cmd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=8)
    _, o, _ = ssh.exec_command(cmd, timeout=10)
    r = o.read().decode().strip()
    ssh.close()
    return r

dominios = ["geniabot","lexelbot","databot","pamibot","cipba"]
for d in dominios:
    code = run(f"curl -sk -o /dev/null -w '%{{http_code}}' --max-time 6 https://{d}.tuexitoprofesional.com.ar/")
    print(f"{d}: {code}")
```

---

## Auditoría y Saneamiento WordPress

### Escaneo de malware
```bash
find /home -maxdepth 6 -path '*/uploads/*.php'
find /tmp -type f -executable
```

### Bloquear XML-RPC (en Traefik o directamente en WP)
Agregar en `wp-config.php`:
```php
add_filter('xmlrpc_enabled', '__return_false');
```

### Resetear password admin via DB (contenedor MariaDB)
```bash
docker exec -it <mariadb_container> mysql -uroot -p<pass> <dbname>
```
```sql
UPDATE wp_users SET user_pass=MD5('NuevaPass123!') WHERE user_login='admin';
```

### Fix dominio en WP Multisite (tras restaurar backup)
```sql
UPDATE wp_blogs SET domain='<dominio_real>';
UPDATE wp_site  SET domain='<dominio_real>';
UPDATE wp_sitemeta SET meta_value='https://<dominio_real>/' WHERE meta_key='siteurl';
UPDATE wp_options SET option_value='https://<dominio_real>' WHERE option_name IN ('siteurl','home');
```

---

## Scripts en `e:\Webs\wp_pythonyn8n\ops\`

| Script | Función |
|---|---|
| `status_bots.py` | Verifica HTTP de todos los bots y lista containers activos |
| `check_resources.py` | RAM, disco, logs Coolify, uso Docker |
| `free_resources.py` | Limpia imágenes/build cache Docker, resetea swap |
| `add_swap_and_deploy.py` | Agrega 4GB swap y dispara redeploy de geniabot |
| `fix_cipba.py` | Verifica DNS cipba y dispara redeploy |
| `debug_futurekids_cipba.py` | Depura contenido de containers y DNS |

---

## Reglas de Oro

1. **`force_https=False` en todos los bots** — Traefik termina el SSL, Flask no debe redirigir.
2. **`frontend/` debe estar en la raíz del repo** — `api.py` lo referencia como `../frontend`.
3. **Swap mínimo 6 GB** antes de buildear bots con chromadb/onnxruntime.
4. **Limpiar build cache Docker** antes de un redeploy si hubo fallos previos: `docker builder prune -af`.
5. **DNS siempre apuntar a `212.85.2.21`** — la IP vieja `181.215.135.56` ya no se usa.
6. **Coolify deploy API usa GET**, no POST: `GET /api/v1/deploy?uuid=<uuid>&force=true`.
7. **Nunca PHP ejecutable en uploads WordPress** — remover inmediatamente.

---

## Checklist ante un bot con 404 o error

- [ ] DNS apunta a `212.85.2.21`: `dig +short <dominio>`
- [ ] Container corriendo: `docker ps | grep <uuid_parcial>`
- [ ] `force_https=False` en `api.py` del container: `docker exec <c> grep force_https /app/api/api.py`
- [ ] `frontend/` presente: `docker exec <c> ls /app/frontend/`
- [ ] RAM disponible para rebuild: `free -h` (mínimo 500MB libres + swap)
- [ ] Redeploy si el código local cambió: `GET /api/v1/deploy?uuid=<uuid>&force=true`

---
*Actualizado Junio 2026 — arquitectura: VPS 212.85.2.21, Coolify + Traefik + Docker*
