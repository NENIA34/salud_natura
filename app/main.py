import json
import urllib.parse
import urllib.request

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from typing import Optional

from app.config import settings
from app.database import init_db, get_db
from app.models import RemedioIn, UsuarioIn, JugoIn, InfusionIn


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/tutorial", StaticFiles(directory="tutorial", html=True), name="tutorial")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "settings": settings,
    })


@app.get("/grimorio")
async def grimorio(request: Request):
    return templates.TemplateResponse("grimorio.html", {
        "request": request,
        "settings": settings,
    })


@app.get("/botiquin")
async def botiquin(request: Request):
    return templates.TemplateResponse("botiquin.html", {
        "request": request,
        "settings": settings,
    })


@app.get("/newsletter")
async def newsletter(request: Request):
    return templates.TemplateResponse("newsletter.html", {
        "request": request,
        "settings": settings,
    })


@app.get("/taller")
async def taller(request: Request):
    return templates.TemplateResponse("taller.html", {
        "request": request,
        "settings": settings,
    })


@app.get("/tutorial")
async def tutorial(request: Request):
    return templates.TemplateResponse("tutorial.html", {
        "request": request,
        "settings": settings,
    })


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/remedios")
async def listar_remedios():
    conn = get_db()
    remedios = [dict(r) for r in conn.execute("SELECT * FROM base_conocimiento_salud").fetchall()]
    conn.close()
    return {"ok": True, "data": remedios}


@app.get("/api/remedios/buscar")
async def buscar_remedios(q: str = Query(..., min_length=1)):
    termino = q.strip()
    patron = f"%{termino}%"
    conn = get_db()
    remedios = [dict(r) for r in conn.execute(
        """
        SELECT *
        FROM base_conocimiento_salud
        WHERE nombre_remedio LIKE ?
           OR propiedades LIKE ?
           OR contraindicaciones LIKE ?
           OR dosificacion LIKE ?
        ORDER BY
            CASE
                WHEN lower(nombre_remedio) = lower(?) THEN 0
                WHEN nombre_remedio LIKE ? THEN 1
                ELSE 2
            END,
            id_remedio
        """,
        (patron, patron, patron, patron, termino, patron),
    ).fetchall()]
    conn.close()
    return {"ok": True, "q": q, "data": remedios}


@app.get("/api/botiquin")
async def listar_botiquin():
    conn = get_db()
    # Calcular índice del grimorio (posición 0-based en lista ordenada por id_remedio)
    idx_map = {r[0]: i for i, r in enumerate(
        conn.execute("SELECT id_remedio FROM base_conocimiento_salud ORDER BY id_remedio").fetchall()
    )}
    rows = []
    for r in conn.execute("SELECT * FROM botiquin ORDER BY id").fetchall():
        item = dict(r)
        item["grimorio_idx"] = idx_map.get(item.get("id_remedio"), None)
        rows.append(item)
    conn.close()
    return {"ok": True, "data": rows}


@app.get("/api/plantas")
async def listar_plantas():
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM base_conocimiento_salud ORDER BY id_remedio").fetchall()]
    conn.close()
    for r in rows:
        img_url = r.get("imagen_url") or ""
        r["imagen"] = img_url.split("/")[-1] if img_url else ""
    return {"ok": True, "plantas": rows}


@app.get("/api/remedios/{id_remedio}")
async def obtener_remedio(id_remedio: int):
    conn = get_db()
    remedio = conn.execute("SELECT * FROM base_conocimiento_salud WHERE id_remedio = ?", (id_remedio,)).fetchone()
    conn.close()
    if not remedio:
        return {"ok": False, "error": "Remedio no encontrado"}
    return {"ok": True, "data": dict(remedio)}


@app.post("/api/remedios")
async def crear_remedio(remedio: RemedioIn):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO base_conocimiento_salud (nombre_remedio, planta_base, propiedades, contraindicaciones, dosificacion, link_articulo_web) VALUES (?, ?, ?, ?, ?, ?)",
        (remedio.nombre_remedio, remedio.planta_base, remedio.propiedades, remedio.contraindicaciones, remedio.dosificacion, remedio.link_articulo_web),
    )
    conn.commit()
    id_nuevo = cursor.lastrowid
    conn.close()
    return {"ok": True, "id_remedio": id_nuevo}


@app.get("/api/usuarios")
async def listar_usuarios():
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM usuarios_y_clientes ORDER BY id_usuario").fetchall()]
    conn.close()
    return {"ok": True, "data": rows}


@app.post("/api/usuarios")
async def registrar_usuario(usuario: UsuarioIn):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO usuarios_y_clientes (nombre_completo, celular, email, password, pais_codigo, direccion_completa, ciudad_prov_pais, latitud, longitud) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (usuario.nombre_completo, usuario.celular, usuario.email, usuario.password, usuario.pais_codigo, usuario.direccion_completa, usuario.ciudad_prov_pais, usuario.latitud, usuario.longitud),
    )
    conn.commit()
    id_nuevo = cursor.lastrowid
    conn.close()
    return {"ok": True, "id_usuario": id_nuevo}


def _geocodificar(direccion: str, ciudad: str):
    q = f"{direccion}, {ciudad}".strip(", ")
    if not q:
        return None, None
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(q)}&format=json&limit=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SaludNatura/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None, None


@app.post("/api/registro")
async def registro_grimorio(usuario: UsuarioIn):
    conn = get_db()
    try:
        existing = conn.execute("SELECT id_usuario FROM usuarios_y_clientes WHERE email = ?", (usuario.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Email ya registrado")
        lat, lon = _geocodificar(usuario.direccion_completa or "", usuario.ciudad_prov_pais or "")
        cursor = conn.execute(
            "INSERT INTO usuarios_y_clientes (nombre_completo, celular, email, password, pais_codigo, direccion_completa, ciudad_prov_pais, latitud, longitud) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (usuario.nombre_completo, usuario.celular, usuario.email, usuario.password, usuario.pais_codigo, usuario.direccion_completa, usuario.ciudad_prov_pais, lat, lon),
        )
        conn.commit()
        id_nuevo = cursor.lastrowid
        row = conn.execute("SELECT * FROM usuarios_y_clientes WHERE id_usuario = ?", (id_nuevo,)).fetchone()
        return {"ok": True, "usuario": dict(row)}
    finally:
        conn.close()


@app.post("/api/login")
async def login_grimorio(payload: dict):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM usuarios_y_clientes WHERE email = ?", (payload.get("email"),)).fetchone()
        if not row or row["password"] != payload.get("password"):
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        return {"ok": True, "usuario": dict(row)}
    finally:
        conn.close()


@app.get("/api/jugos")
async def listar_jugos():
    import json as _json
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM jugos ORDER BY id").fetchall()]
    conn.close()
    for r in rows:
        r['ingredientes'] = _json.loads(r['ingredientes']) if r.get('ingredientes') else []
        r['pasos'] = _json.loads(r['pasos']) if r.get('pasos') else []
    return {"ok": True, "data": rows}


@app.get("/api/infusiones")
async def listar_infusiones():
    import json as _json
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM infusiones ORDER BY id").fetchall()]
    conn.close()
    for r in rows:
        r['ingredientes'] = _json.loads(r['ingredientes']) if r.get('ingredientes') else []
        r['pasos'] = _json.loads(r['pasos']) if r.get('pasos') else []
    return {"ok": True, "data": rows}


@app.get("/api/tiendas")
async def tiendas_cercanas(lat: float, lon: float):
    return {"ok": True, "tiendas": []}


@app.post("/api/geocodificar")
async def geocodificar_usuario(payload: dict):
    lat, lon = _geocodificar(payload.get("direccion_completa", ""), payload.get("ciudad_prov_pais", ""))
    return {"ok": True, "lat": lat, "lon": lon}


# ── Admin ──

@app.get("/admin")
async def admin_inicio(request: Request):
    conn = get_db()
    total_remedios   = conn.execute("SELECT COUNT(*) FROM base_conocimiento_salud").fetchone()[0]
    total_usuarios   = conn.execute("SELECT COUNT(*) FROM usuarios_y_clientes").fetchone()[0]
    total_botiquin   = conn.execute("SELECT COUNT(*) FROM botiquin").fetchone()[0]
    total_jugos      = conn.execute("SELECT COUNT(*) FROM jugos").fetchone()[0]
    total_infusiones = conn.execute("SELECT COUNT(*) FROM infusiones").fetchone()[0]
    conn.close()
    return templates.TemplateResponse("admin_inicio.html", {
        "request": request, "settings": settings, "seccion": "inicio",
        "total_remedios": total_remedios, "total_usuarios": total_usuarios,
        "total_botiquin": total_botiquin, "total_jugos": total_jugos,
        "total_infusiones": total_infusiones,
    })


@app.get("/admin/remedios")
async def admin_remedios(request: Request, mensaje: Optional[str] = None):
    conn = get_db()
    remedios = conn.execute("SELECT * FROM base_conocimiento_salud ORDER BY id_remedio DESC").fetchall()
    conn.close()
    return templates.TemplateResponse("admin_remedios.html", {
        "request": request, "settings": settings, "seccion": "remedios",
        "remedios": remedios, "mensaje": mensaje,
    })


@app.post("/admin/remedios/guardar")
async def admin_remedios_guardar(
    nombre_remedio: str = Form(...),
    planta_base: str = Form(""),
    propiedades: str = Form(""),
    contraindicaciones: str = Form(""),
    dosificacion: str = Form(""),
    link_articulo_web: str = Form(""),
    imagen_url: str = Form(""),
    id_remedio: str = Form(""),
):
    conn = get_db()
    if id_remedio:
        conn.execute(
            "UPDATE base_conocimiento_salud SET nombre_remedio=?, planta_base=?, propiedades=?, contraindicaciones=?, dosificacion=?, link_articulo_web=?, imagen_url=? WHERE id_remedio=?",
            (nombre_remedio, planta_base or None, propiedades or None, contraindicaciones or None, dosificacion or None, link_articulo_web or None, imagen_url or None, int(id_remedio)),
        )
        mensaje = "Remedio actualizado"
    else:
        conn.execute(
            "INSERT INTO base_conocimiento_salud (nombre_remedio, planta_base, propiedades, contraindicaciones, dosificacion, link_articulo_web, imagen_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nombre_remedio, planta_base or None, propiedades or None, contraindicaciones or None, dosificacion or None, link_articulo_web or None, imagen_url or None),
        )
        mensaje = "Remedio creado"
    conn.commit()
    conn.close()
    return RedirectResponse(f"/admin/remedios?mensaje={mensaje}", status_code=303)


@app.post("/admin/remedios/{id_remedio}/eliminar")
async def admin_remedios_eliminar(id_remedio: int):
    conn = get_db()
    conn.execute("DELETE FROM base_conocimiento_salud WHERE id_remedio=?", (id_remedio,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/remedios?mensaje=Remedio eliminado", status_code=303)


@app.get("/admin/botiquin")
async def admin_botiquin(request: Request, mensaje: Optional[str] = None):
    conn = get_db()
    items = conn.execute("SELECT * FROM botiquin ORDER BY id").fetchall()
    conn.close()
    return templates.TemplateResponse("admin_botiquin.html", {
        "request": request, "settings": settings, "items": items, "mensaje": mensaje,
    })


@app.post("/admin/botiquin/guardar")
async def admin_botiquin_guardar(
    dolencia: str = Form(...),
    emoji: str = Form(""),
    categoria: str = Form(""),
    planta: str = Form(""),
    nombre_cientifico: str = Form(""),
    preparacion: str = Form(""),
    nota: str = Form(""),
    id: str = Form(""),
):
    conn = get_db()
    if id:
        conn.execute(
            "UPDATE botiquin SET dolencia=?, emoji=?, categoria=?, planta=?, nombre_cientifico=?, preparacion=?, nota=? WHERE id=?",
            (dolencia, emoji, categoria, planta, nombre_cientifico, preparacion, nota, int(id)),
        )
        mensaje = "Dolencia actualizada"
    else:
        conn.execute(
            "INSERT INTO botiquin (dolencia, emoji, categoria, planta, nombre_cientifico, preparacion, nota) VALUES (?,?,?,?,?,?,?)",
            (dolencia, emoji, categoria, planta, nombre_cientifico, preparacion, nota),
        )
        mensaje = "Dolencia creada"
    conn.commit()
    conn.close()
    return RedirectResponse(f"/admin/botiquin?mensaje={mensaje}", status_code=303)


@app.post("/admin/botiquin/{id}/eliminar")
async def admin_botiquin_eliminar(id: int):
    conn = get_db()
    conn.execute("DELETE FROM botiquin WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/botiquin?mensaje=Dolencia eliminada", status_code=303)


@app.get("/admin/usuarios")
async def admin_usuarios(request: Request, mensaje: Optional[str] = None):
    conn = get_db()
    usuarios = conn.execute("SELECT * FROM usuarios_y_clientes ORDER BY id_usuario DESC").fetchall()
    conn.close()
    return templates.TemplateResponse("admin_usuarios.html", {
        "request": request, "settings": settings, "seccion": "usuarios",
        "usuarios": usuarios, "mensaje": mensaje,
    })


@app.post("/admin/usuarios/guardar")
async def admin_usuarios_guardar(
    nombre_completo: str = Form(...),
    celular: str = Form(""),
    email: str = Form(""),
    direccion_completa: str = Form(""),
    ciudad_prov_pais: str = Form(""),
    latitud: str = Form(""),
    longitud: str = Form(""),
    id_usuario: str = Form(""),
):
    lat = float(latitud) if latitud else None
    lon = float(longitud) if longitud else None
    conn = get_db()
    if id_usuario:
        conn.execute(
            "UPDATE usuarios_y_clientes SET nombre_completo=?, celular=?, email=?, direccion_completa=?, ciudad_prov_pais=?, latitud=?, longitud=? WHERE id_usuario=?",
            (nombre_completo, celular or None, email or None, direccion_completa or None, ciudad_prov_pais or None, lat, lon, int(id_usuario)),
        )
        mensaje = "Usuario actualizado"
    else:
        conn.execute(
            "INSERT INTO usuarios_y_clientes (nombre_completo, celular, email, direccion_completa, ciudad_prov_pais, latitud, longitud) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nombre_completo, celular or None, email or None, direccion_completa or None, ciudad_prov_pais or None, lat, lon),
        )
        mensaje = "Usuario creado"
    conn.commit()
    conn.close()
    return RedirectResponse(f"/admin/usuarios?mensaje={mensaje}", status_code=303)


@app.post("/admin/usuarios/{id_usuario}/eliminar")
async def admin_usuarios_eliminar(id_usuario: int):
    conn = get_db()
    conn.execute("DELETE FROM usuarios_y_clientes WHERE id_usuario=?", (id_usuario,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/usuarios?mensaje=Usuario eliminado", status_code=303)


@app.get("/admin/jugos")
async def admin_jugos(request: Request, mensaje: Optional[str] = None):
    conn = get_db()
    jugos = conn.execute("SELECT j.*, b.nombre_remedio FROM jugos j LEFT JOIN base_conocimiento_salud b ON j.id_remedio = b.id_remedio ORDER BY j.id").fetchall()
    remedios = conn.execute("SELECT id_remedio, nombre_remedio FROM base_conocimiento_salud ORDER BY nombre_remedio").fetchall()
    conn.close()
    return templates.TemplateResponse("admin_jugos.html", {
        "request": request, "settings": settings,
        "jugos": jugos, "remedios": remedios, "mensaje": mensaje,
    })


@app.post("/admin/jugos/guardar")
async def admin_jugos_guardar(
    nombre: str = Form(...),
    tag: str = Form(""),
    foto_url: str = Form(""),
    ingredientes: str = Form(""),
    pasos: str = Form(""),
    beneficio: str = Form(""),
    id_remedio: str = Form(""),
    id: str = Form(""),
):
    import json
    ing_list = [x.strip() for x in ingredientes.splitlines() if x.strip()]
    pasos_list = [x.strip() for x in pasos.splitlines() if x.strip()]
    ing_json = json.dumps(ing_list, ensure_ascii=False)
    pasos_json = json.dumps(pasos_list, ensure_ascii=False)
    id_rem = int(id_remedio) if id_remedio else None
    conn = get_db()
    if id:
        conn.execute(
            "UPDATE jugos SET nombre=?, tag=?, foto_url=?, ingredientes=?, pasos=?, beneficio=?, id_remedio=? WHERE id=?",
            (nombre, tag or None, foto_url or None, ing_json, pasos_json, beneficio or None, id_rem, int(id)),
        )
        mensaje = "Jugo actualizado"
    else:
        conn.execute(
            "INSERT INTO jugos (nombre, tag, foto_url, ingredientes, pasos, beneficio, id_remedio) VALUES (?,?,?,?,?,?,?)",
            (nombre, tag or None, foto_url or None, ing_json, pasos_json, beneficio or None, id_rem),
        )
        mensaje = "Jugo creado"
    conn.commit()
    conn.close()
    return RedirectResponse(f"/admin/jugos?mensaje={mensaje}", status_code=303)


@app.post("/admin/jugos/{id}/eliminar")
async def admin_jugos_eliminar(id: int):
    conn = get_db()
    conn.execute("DELETE FROM jugos WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/jugos?mensaje=Jugo eliminado", status_code=303)


@app.get("/admin/infusiones")
async def admin_infusiones(request: Request, mensaje: Optional[str] = None):
    conn = get_db()
    infusiones = conn.execute("SELECT i.*, b.nombre_remedio FROM infusiones i LEFT JOIN base_conocimiento_salud b ON i.id_remedio = b.id_remedio ORDER BY i.id").fetchall()
    remedios = conn.execute("SELECT id_remedio, nombre_remedio FROM base_conocimiento_salud ORDER BY nombre_remedio").fetchall()
    conn.close()
    return templates.TemplateResponse("admin_infusiones.html", {
        "request": request, "settings": settings,
        "infusiones": infusiones, "remedios": remedios, "mensaje": mensaje,
    })


@app.post("/admin/infusiones/guardar")
async def admin_infusiones_guardar(
    nombre: str = Form(...),
    tag: str = Form(""),
    foto_url: str = Form(""),
    ingredientes: str = Form(""),
    pasos: str = Form(""),
    beneficio: str = Form(""),
    id_remedio: str = Form(""),
    id: str = Form(""),
):
    import json
    ing_list = [x.strip() for x in ingredientes.splitlines() if x.strip()]
    pasos_list = [x.strip() for x in pasos.splitlines() if x.strip()]
    ing_json = json.dumps(ing_list, ensure_ascii=False)
    pasos_json = json.dumps(pasos_list, ensure_ascii=False)
    id_rem = int(id_remedio) if id_remedio else None
    conn = get_db()
    if id:
        conn.execute(
            "UPDATE infusiones SET nombre=?, tag=?, foto_url=?, ingredientes=?, pasos=?, beneficio=?, id_remedio=? WHERE id=?",
            (nombre, tag or None, foto_url or None, ing_json, pasos_json, beneficio or None, id_rem, int(id)),
        )
        mensaje = "Infusión actualizada"
    else:
        conn.execute(
            "INSERT INTO infusiones (nombre, tag, foto_url, ingredientes, pasos, beneficio, id_remedio) VALUES (?,?,?,?,?,?,?)",
            (nombre, tag or None, foto_url or None, ing_json, pasos_json, beneficio or None, id_rem),
        )
        mensaje = "Infusión creada"
    conn.commit()
    conn.close()
    return RedirectResponse(f"/admin/infusiones?mensaje={mensaje}", status_code=303)


@app.post("/admin/infusiones/{id}/eliminar")
async def admin_infusiones_eliminar(id: int):
    conn = get_db()
    conn.execute("DELETE FROM infusiones WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/infusiones?mensaje=Infusión eliminada", status_code=303)
