
from flask import Flask, request, render_template, redirect, url_for, flash, session
import psycopg2
from argon2 import PasswordHasher
import cloudinary, cloudinary.uploader

app = Flask(__name__)
app.secret_key = "cambia_esto_por_uno_mas_secreto"
ph = PasswordHasher()

# Cloudinary (ya las tenías)
cloudinary.config(
    cloud_name="dcg4vdtld",
    api_key="666673213594632",
    api_secret="y7aMpLhDG8vdij3EyWOL2qFxcDs",
    secure=True
)

DB_URL = "postgres://019a50a7-1e83-7246-a69e-ff4d795a0245:3160f647-d6a1-42f2-b742-8778de0027cb@us-west-2.db.thenile.dev:5432/market"

def get_conn():
    return psycopg2.connect(DB_URL)

# decoradores
def login_required(view):
    from functools import wraps
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    from functools import wraps
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("id_rol") != 1:
            flash("No tienes permisos para acceder.", "error")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped

@app.route("/")
def index():
    conn = get_conn(); cur = conn.cursor()
    # publicaciones con joins
    try:
        cur.execute("""SELECT p.id_publicacion,
                               p.titulo,
                               COALESCE(p.descripcion,''),
                               p.precio,
                               p.moneda,
                               p.creado_en,
                               c.nombre,
                               s.nombre,
                               t.tipo,
                               m.marca,
                               COALESCE(p.id_categoria,0),
                               COALESCE(p.id_sub_categoria,0),
                               COALESCE(p.id_marca,0),
                               e.estado,
                               COALESCE(p.id_estado,0)
                        FROM public.publicaciones p
                        LEFT JOIN public.categoria c ON p.id_categoria=c.id_categoria
                        LEFT JOIN public.sub_categoria s ON p.id_sub_categoria=s.id_sub_categoria
                        LEFT JOIN public.tipo t ON p.id_tipo = t.id_tipo
                        LEFT JOIN public.marca m ON p.id_marca = m.id_marca
                        LEFT JOIN public.estado e ON p.id_estado = e.id_estado
                        ORDER BY p.creado_en DESC""")
        pubs = cur.fetchall()
        has_brand = True
    except Exception:
        # fallback sin marca / ids
        cur.execute("""SELECT p.id_publicacion,
                               p.titulo,
                               COALESCE(p.descripcion,''),
                               p.precio,
                               p.moneda,
                               p.creado_en,
                               c.nombre,
                               s.nombre,
                               t.tipo,
                               NULL AS marca,
                               COALESCE(p.id_categoria,0),
                               COALESCE(p.id_sub_categoria,0),
                               0 AS id_marca,
                               e.estado,
                               COALESCE(p.id_estado,0)
                        FROM public.publicaciones p
                        LEFT JOIN public.categoria c ON p.id_categoria=c.id_categoria
                        LEFT JOIN public.sub_categoria s ON p.id_sub_categoria=s.id_sub_categoria
                        LEFT JOIN public.tipo t ON p.id_tipo = t.id_tipo
                        LEFT JOIN public.estado e ON p.id_estado = e.id_estado
                        FROM public.publicaciones p
                        LEFT JOIN public.categoria c ON p.id_categoria=c.id_categoria
                        LEFT JOIN public.sub_categoria s ON p.id_sub_categoria=s.id_sub_categoria
                        LEFT JOIN public.tipo t ON p.id_tipo = t.id_tipo
                        ORDER BY p.creado_en DESC""")
        pubs = cur.fetchall()
        has_brand = False

    # imágenes
    cur.execute("SELECT id_publicacion, url_imagen FROM public.publicacion_imagen ORDER BY id_imagen")
    imgs = cur.fetchall()

    # datos para filtros
    cur.execute("SELECT id_categoria, nombre, COALESCE(id_tipo,0) FROM public.categoria ORDER BY nombre")
    categorias = cur.fetchall()
    # mover 'Otros' al final
    categorias = sorted(categorias, key=lambda x: (x[1].strip().lower() == 'otros', x[1].lower()))

    cur.execute("SELECT id_tipo, tipo FROM public.tipo ORDER BY tipo")
    tipos = cur.fetchall()

    cur.execute("SELECT id_sub_categoria, id_categoria, nombre FROM public.sub_categoria ORDER BY nombre")
    subcategorias = cur.fetchall()
    subcategorias = sorted(subcategorias, key=lambda x: (x[2].strip().lower() == 'otros', x[2].lower()))

    cur.execute("SELECT id_marca, marca, COALESCE(id_sub_categoria,0) FROM public.marca ORDER BY marca")
    marcas = cur.fetchall()
    marcas = sorted(marcas, key=lambda x: (x[1].strip().lower() == 'otros', x[1].lower()))

    cur.execute("SELECT id_estado, estado FROM public.estado ORDER BY estado")
    estados = cur.fetchall()

    cur.close(); conn.close()

    img_map = {}
    for pid, url in imgs:
        if pid not in img_map:
            img_map[pid] = url

    return render_template("public_publicaciones.html",
                           publicaciones=pubs,
                           img_map=img_map,
                           categorias=categorias,
                           subcategorias=subcategorias,
                           marcas=marcas,
                           tipos=tipos,
                           estados=estados)


@app.route("/publicacion/<int:pub_id>")
def publicacion_detalle(pub_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""SELECT p.id_publicacion,
                          p.titulo,
                          COALESCE(p.descripcion,''),
                          p.precio,
                          p.moneda,
                          p.creado_en,
                          c.nombre,
                          s.nombre,
                          t.tipo,
                          u.nombre,
                          u.apellido,
                          u.correo,
                          u.celular,
                          m.marca,
                          e.estado
                   FROM public.publicaciones p
                   LEFT JOIN public.categoria c ON p.id_categoria=c.id_categoria
                   LEFT JOIN public.sub_categoria s ON p.id_sub_categoria=s.id_sub_categoria
                   LEFT JOIN public.tipo t ON p.id_tipo = t.id_tipo
                   LEFT JOIN public.usuarios u ON p.id_usuario = u.id_usuario
                   LEFT JOIN public.marca m ON p.id_marca = m.id_marca
                   LEFT JOIN public.estado e ON p.id_estado = e.id_estado
                   WHERE p.id_publicacion = %s""",
                (pub_id,))
    pub = cur.fetchone()

    if not pub:
        cur.close(); conn.close()
        return "Publicación no encontrada", 404

    cur.execute("""SELECT url_imagen FROM public.publicacion_imagen
                   WHERE id_publicacion = %s
                   ORDER BY id_imagen""",
                (pub_id,))
    imagenes = [r[0] for r in cur.fetchall()]
    cur.close(); conn.close()
    return render_template("public_publicacion_detalle.html",
                           pub=pub,
                           imagenes=imagenes)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        password = request.form.get("password")

        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id_usuario, usuario, password_hash, id_rol FROM public.usuarios WHERE usuario = %s", (usuario,))
        row = cur.fetchone()
        cur.close(); conn.close()

        if not row:
            flash("Usuario o contraseña incorrectos", "error")
            return render_template("login.html")

        uid, uname, phash, id_rol = row

        if not phash:
            flash("Este usuario no tiene contraseña configurada.", "error")
            return render_template("login.html")

        try:
            ph.verify(phash, password)
        except Exception:
            flash("Usuario o contraseña incorrectos", "error")
            return render_template("login.html")

        # guardar sesión
        session["user_id"] = uid
        session["usuario"] = uname
        session["id_rol"] = id_rol

        # si es admin lo mandamos al panel
        if id_rol == 1:
            return redirect(url_for("admin_panel"))
        # si no, lo mandamos al inicio
        return redirect(url_for("index"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# PANEL PRINCIPAL
@app.route("/admin")
@admin_required
def admin_panel():
    return render_template("admin_panel.html", usuario=session.get("usuario"))

# 1. CATEGORÍAS
@app.route("/admin/categorias", methods=["GET","POST"])
@admin_required
def admin_categorias():
    conn = get_conn(); cur = conn.cursor()
    # traemos tipos para asignar la categoría al tipo
    cur.execute("SELECT id_tipo, tipo FROM public.tipo ORDER BY tipo")
    tipos = cur.fetchall()

    if request.method == "POST":
        id_categoria = request.form.get("id_categoria")  # para editar
        nombre = request.form.get("nombre")
        id_tipo = request.form.get("id_tipo") or None

        if id_categoria:  # update
            cur.execute("UPDATE public.categoria SET nombre=%s, id_tipo=%s WHERE id_categoria=%s",
                        (nombre, id_tipo, id_categoria))
            flash("Categoría actualizada", "success")
        else:  # insert
            cur.execute("INSERT INTO public.categoria (nombre, id_tipo) VALUES (%s,%s)",
                        (nombre, id_tipo))
            flash("Categoría creada", "success")
        conn.commit()

    cur.execute("""SELECT c.id_categoria, c.nombre, COALESCE(t.tipo,'') AS tipo
                   FROM public.categoria c
                   LEFT JOIN public.tipo t ON c.id_tipo = t.id_tipo
                   ORDER BY c.nombre""")
    categorias = cur.fetchall()
    cur.close(); conn.close()
    return render_template("admin_categorias.html", categorias=categorias, tipos=tipos)

# 2. SUBCATEGORÍAS
@app.route("/admin/subcategorias", methods=["GET","POST"])
@admin_required
def admin_subcategorias():
    conn = get_conn(); cur = conn.cursor()
    # necesitamos categorias para asociar
    cur.execute("SELECT id_categoria, nombre FROM public.categoria ORDER BY nombre")
    categorias = cur.fetchall()

    if request.method == "POST":
        id_sub = request.form.get("id_sub_categoria")
        nombre = request.form.get("nombre")
        id_categoria = request.form.get("id_categoria") or None

        if id_sub:
            cur.execute("UPDATE public.sub_categoria SET nombre=%s, id_categoria=%s WHERE id_sub_categoria=%s",
                        (nombre, id_categoria, id_sub))
            flash("Subcategoría actualizada", "success")
        else:
            cur.execute("INSERT INTO public.sub_categoria (id_categoria, nombre) VALUES (%s,%s)",
                        (id_categoria, nombre))
            flash("Subcategoría creada", "success")
        conn.commit()

    cur.execute("""SELECT s.id_sub_categoria, s.nombre, c.nombre
                   FROM public.sub_categoria s
                   LEFT JOIN public.categoria c ON s.id_categoria = c.id_categoria
                   ORDER BY s.nombre""")
    subcategorias = cur.fetchall()
    cur.close(); conn.close()
    return render_template("admin_subcategorias.html", subcategorias=subcategorias, categorias=categorias)

# 3. TIPOS
@app.route("/admin/tipos", methods=["GET","POST"])
@admin_required
def admin_tipos():
    conn = get_conn(); cur = conn.cursor()
    if request.method == "POST":
        id_tipo = request.form.get("id_tipo")
        tipo = request.form.get("tipo")
        if id_tipo:
            cur.execute("UPDATE public.tipo SET tipo=%s WHERE id_tipo=%s", (tipo, id_tipo))
            flash("Tipo actualizado", "success")
        else:
            cur.execute("INSERT INTO public.tipo (tipo) VALUES (%s)", (tipo,))
            flash("Tipo creado", "success")
        conn.commit()
    cur.execute("SELECT id_tipo, tipo FROM public.tipo ORDER BY tipo")
    tipos = cur.fetchall()
    cur.close(); conn.close()
    return render_template("admin_tipos.html", tipos=tipos)

# 4. MARCAS
@app.route("/admin/marcas", methods=["GET", "POST"])
@admin_required
def admin_marcas():
    conn = get_conn(); cur = conn.cursor()
    # subcategorías para el combo
    cur.execute("SELECT id_sub_categoria, nombre FROM public.sub_categoria ORDER BY nombre")
    subcats = cur.fetchall()

    if request.method == "POST":
        marca = request.form.get("marca")
        id_sub_categoria = request.form.get("id_sub_categoria") or None
        if marca:
            cur.execute(
                "INSERT INTO public.marca (marca, id_sub_categoria) VALUES (%s, %s)",
                (marca, id_sub_categoria)
            )
            conn.commit()
            flash("Marca guardada", "success")

    cur.execute("""
        SELECT m.id_marca, m.marca, s.nombre
        FROM public.marca m
        LEFT JOIN public.sub_categoria s ON m.id_sub_categoria = s.id_sub_categoria
        ORDER BY m.marca
    """)
    marcas = cur.fetchall()
    cur.close(); conn.close()
    return render_template("admin_marcas.html", subcats=subcats, marcas=marcas)

# 5. ESTADOS
@app.route("/admin/estados", methods=["GET", "POST"])
@admin_required
def admin_estados():
    conn = get_conn(); cur = conn.cursor()
    if request.method == "POST":
        estado = request.form.get("estado")
        if estado:
            cur.execute("INSERT INTO public.estado (estado) VALUES (%s)", (estado,))
            conn.commit()
            flash("Estado guardado", "success")

    cur.execute("SELECT id_estado, estado FROM public.estado ORDER BY estado")
    estados = cur.fetchall()
    cur.close(); conn.close()
    return render_template("admin_estados.html", estados=estados)

# 4. VER PUBLICACIONES
@app.route("/admin/publicaciones")
@admin_required
def admin_publicaciones():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""SELECT p.id_publicacion,
                           p.titulo,
                           COALESCE(p.descripcion,''),
                           p.precio,
                           p.moneda,
                           p.creado_en,
                           c.nombre,
                           s.nombre,
                           t.tipo
                    FROM public.publicaciones p
                    LEFT JOIN public.categoria c ON p.id_categoria=c.id_categoria
                    LEFT JOIN public.sub_categoria s ON p.id_sub_categoria=s.id_sub_categoria
                    LEFT JOIN public.tipo t ON p.id_tipo = t.id_tipo
                    ORDER BY p.creado_en DESC""")
    pubs = cur.fetchall()
    cur.execute("SELECT id_publicacion, url_imagen FROM public.publicacion_imagen ORDER BY id_imagen")
    imgs = cur.fetchall(); cur.close(); conn.close()
    img_map = {}
    for pid, url in imgs:
        if pid not in img_map:
            img_map[pid] = url
    return render_template("admin_publicaciones.html", publicaciones=pubs, img_map=img_map)

# formulario público de nueva publicación (igual que antes, lo dejo sencillo)
@app.route("/publicar", methods=["GET","POST"])
def publicar():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id_categoria, nombre, COALESCE(id_tipo,0) FROM public.categoria ORDER BY nombre")
    categorias = cur.fetchall()
    categorias = sorted(categorias, key=lambda x: (x[1].strip().lower() == 'otros', x[1].lower()))

    cur.execute("SELECT id_sub_categoria, id_categoria, nombre FROM public.sub_categoria ORDER BY nombre")
    subcategorias = cur.fetchall()
    subcategorias = sorted(subcategorias, key=lambda x: (x[2].strip().lower() == 'otros', x[2].lower()))

    cur.execute("SELECT id_tipo, tipo FROM public.tipo ORDER BY tipo")
    tipos = cur.fetchall()

    cur.execute("SELECT id_marca, marca, COALESCE(id_sub_categoria,0) FROM public.marca ORDER BY marca")
    marcas = cur.fetchall()
    marcas = sorted(marcas, key=lambda x: (x[1].strip().lower() == 'otros', x[1].lower()))

    cur.execute("SELECT id_estado, estado FROM public.estado ORDER BY estado")
    estados = cur.fetchall()
    cur.execute("SELECT id_estado, estado FROM public.estado ORDER BY estado")
    estados = cur.fetchall()

    if request.method == "POST":
        nombre = request.form.get("nombre")
        apellido = request.form.get("apellido")
        correo = request.form.get("correo")
        celular = request.form.get("celular")

        id_tipo = request.form.get("id_tipo") or None
        titulo = request.form.get("titulo")
        descripcion = request.form.get("descripcion")
        precio = request.form.get("precio")
        moneda = request.form.get("moneda") or "Q"
        id_categoria = request.form.get("id_categoria") or None
        id_sub_categoria = request.form.get("id_sub_categoria") or None
        id_marca = request.form.get("id_marca") or None
        id_estado = request.form.get("id_estado") or None

        # usuario por celular
        cur.execute("SELECT id_usuario FROM public.usuarios WHERE usuario = %s", (celular,))
        row = cur.fetchone()
        if row:
            id_usuario = row[0]
        else:
            cur.execute("""INSERT INTO public.usuarios
                           (nombre, apellido, correo, celular, usuario, ubicacion, creado_en,
                            password_hash, debe_cambiar_password, id_rol)
                           VALUES (%s,%s,%s,%s,%s,NULL,NOW(),NULL,false,2)
                           RETURNING id_usuario""",
                        (nombre, apellido, correo, celular, celular))
            id_usuario = cur.fetchone()[0]

        # intento con marca y estado (si las columnas existen)
        try:
            cur.execute("""INSERT INTO public.publicaciones
                           (id_usuario, id_tipo, id_categoria, id_sub_categoria, id_marca, id_estado,
                            titulo, descripcion, precio, moneda,
                            estado_publicacion, creado_en, actualizado_en)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'activo',NOW(),NOW())
                           RETURNING id_publicacion""",
                        (id_usuario, id_tipo, id_categoria, id_sub_categoria, id_marca, id_estado,
                         titulo, descripcion, precio, moneda))
        except Exception:
            cur.execute("""INSERT INTO public.publicaciones
                           (id_usuario, id_tipo, id_categoria, id_sub_categoria, titulo, descripcion, precio, moneda,
                            estado_publicacion, creado_en, actualizado_en)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'activo',NOW(),NOW())
                           RETURNING id_publicacion""",
                        (id_usuario, id_tipo, id_categoria, id_sub_categoria, titulo, descripcion, precio, moneda))
        id_pub = cur.fetchone()[0]

        # imágenes
        files = request.files.getlist("imagenes")
        portada_idx_str = request.form.get("portada_index", "0")
        try:
            portada_idx = int(portada_idx_str)
        except ValueError:
            portada_idx = 0

        ordered_files = []
        if files:
            # primero la que el usuario marcó como portada
            if 0 <= portada_idx < len(files):
                ordered_files.append(files[portada_idx])
            # luego las demás
            for i, f in enumerate(files):
                if i == portada_idx:
                    continue
                ordered_files.append(f)
        else:
            ordered_files = []

        for f in ordered_files[:10]:
            if f and f.filename:
                up = cloudinary.uploader.upload(f)
                cur.execute("""INSERT INTO public.publicacion_imagen
                               (id_publicacion, url_imagen, public_id)
                               VALUES (%s,%s,%s)""",
                            (id_pub, up.get("secure_url"), up.get("public_id")))

        conn.commit(); cur.close(); conn.close()
        flash("Publicación enviada", "success")
        return redirect(url_for("index"))

    cur.close(); conn.close()
    return render_template("nueva_publicacion.html",
                           categorias=categorias,
                           subcategorias=subcategorias,
                           tipos=tipos,
                           marcas=marcas,
                           estados=estados)



# ADMIN - PUBLICACIONES (extensiones)
@app.route("/admin/publicaciones/<int:id_publicacion>/eliminar", methods=["GET","POST"])
@admin_required
def admin_eliminar_publicacion(id_publicacion):
    conn = get_conn(); cur = conn.cursor()
    # primero borramos las imágenes relacionadas
    cur.execute("DELETE FROM public.publicacion_imagen WHERE id_publicacion = %s", (id_publicacion,))
    # luego la publicación
    cur.execute("DELETE FROM public.publicaciones WHERE id_publicacion = %s", (id_publicacion,))
    conn.commit()
    cur.close(); conn.close()
    flash("Publicación eliminada", "success")
    return redirect(url_for("admin_publicaciones"))


@app.route("/admin/publicaciones/<int:id_publicacion>/editar", methods=["GET","POST"])
@admin_required
def admin_editar_publicacion(id_publicacion):
    conn = get_conn(); cur = conn.cursor()
    if request.method == "POST":
        id_tipo = request.form.get("id_tipo") or None
        id_categoria = request.form.get("id_categoria") or None
        id_sub_categoria = request.form.get("id_sub_categoria") or None
        id_marca = request.form.get("id_marca") or None
        id_estado = request.form.get("id_estado") or None
        titulo = request.form.get("titulo")
        descripcion = request.form.get("descripcion")
        precio = request.form.get("precio") or 0
        moneda = request.form.get("moneda") or "Q"

        cur.execute("""
            UPDATE public.publicaciones
               SET id_tipo = %s,
                   id_categoria = %s,
                   id_sub_categoria = %s,
                   id_marca = %s,
                   id_estado = %s,
                   titulo = %s,
                   descripcion = %s,
                   precio = %s,
                   moneda = %s,
                   actualizado_en = NOW()
             WHERE id_publicacion = %s
        """, (id_tipo, id_categoria, id_sub_categoria, id_marca, id_estado,
              titulo, descripcion, precio, moneda, id_publicacion))
        conn.commit()
        cur.close(); conn.close()
        flash("Publicación actualizada", "success")
        return redirect(url_for("admin_publicaciones"))
    else:
        # datos de la publicación
        cur.execute("""
            SELECT id_publicacion,
                   id_usuario,
                   id_tipo,
                   id_categoria,
                   id_sub_categoria,
                   id_marca,
                   id_estado,
                   titulo,
                   descripcion,
                   precio,
                   moneda
              FROM public.publicaciones
             WHERE id_publicacion = %s
        """, (id_publicacion,))
        publicacion = cur.fetchone()

        # datos del vendedor
        usuario = None
        if publicacion and publicacion[1]:
            cur.execute("""
                SELECT nombre, apellido, correo, celular
                  FROM public.usuarios
                 WHERE id_usuario = %s
            """, (publicacion[1],))
            usuario = cur.fetchone()
        else:
            usuario = ("", "", "", "")

        # imágenes
        cur.execute("""
            SELECT id_imagen, url_imagen, public_id
              FROM public.publicacion_imagen
             WHERE id_publicacion = %s
             ORDER BY id_imagen
        """, (id_publicacion,))
        imagenes = cur.fetchall()

        # catálogos
        cur.execute("SELECT id_categoria, nombre FROM public.categoria ORDER BY nombre")
        categorias = cur.fetchall()
        cur.execute("SELECT id_sub_categoria, id_categoria, nombre FROM public.sub_categoria ORDER BY nombre")
        subcategorias = cur.fetchall()
        cur.execute("SELECT id_tipo, tipo FROM public.tipo ORDER BY tipo")
        tipos = cur.fetchall()
        cur.execute("SELECT id_marca, marca, id_sub_categoria FROM public.marca ORDER BY marca")
        marcas = cur.fetchall()
        cur.execute("SELECT id_estado, estado FROM public.estado ORDER BY estado")
        estados = cur.fetchall()

        cur.close(); conn.close()
        return render_template(
            "editar_publicacion.html",
            publicacion=publicacion,
            usuario=usuario,
            imagenes=imagenes,
            categorias=categorias,
            subcategorias=subcategorias,
            tipos=tipos,
            marcas=marcas,
            estados=estados,
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
