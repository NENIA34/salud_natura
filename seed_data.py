"""
Seed inicial: carga las 21 hierbas del Grimorio en la base de datos.
Ejecutar: python seed_data.py
"""
import sqlite3, os, sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'salud_natura.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.execute('''CREATE TABLE IF NOT EXISTS base_conocimiento_salud (
    id_remedio INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_remedio TEXT NOT NULL,
    planta_base TEXT,
    propiedades TEXT,
    contraindicaciones TEXT,
    dosificacion TEXT,
    link_articulo_web TEXT
)''')
conn.execute('''CREATE TABLE IF NOT EXISTS usuarios_y_clientes (
    id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_completo TEXT NOT NULL,
    celular TEXT,
    email TEXT,
    direccion_completa TEXT,
    ciudad_prov_pais TEXT,
    latitud REAL,
    longitud REAL
)''')

# nombre_remedio: sin tildes para que nombreToImg() del grimorio genere la URL correcta
hierbas = [
     ('Manzanilla verde y amarilla',   'Matricaria chamomilla',   'Antiinflamatoria,Sedante suave,Digestiva,Antibacteriana,Antiespasmódica',
     'La infusión debe reposar tapada 10 min para conservar sus aceites esenciales.',
     'Alivia insomnio y nerviosismo, calma cólicos y gastritis. En piel reduce rojeces e irritaciones.'),
    ('Manzanilla',   'Matricaria chamomilla',   'Antiinflamatoria,Sedante suave,Digestiva,Antibacteriana,Antiespasmódica',
     'La infusión debe reposar tapada 10 min para conservar sus aceites esenciales.',
     'Alivia insomnio y nerviosismo, calma cólicos y gastritis. En piel reduce rojeces e irritaciones.'),
    ('Menta',        'Mentha x piperita',        'Digestiva,Analgésica,Refrescante,Antiespasmódica,Descongestionante',
     'Evitar en niños menores de 2 años. No usar aceite esencial puro sin diluir.',
     'Reduce náuseas, flatulencias y espasmos intestinales. El mentol actúa sobre cefaleas tensionales.'),
    ('Lavanda',      'Lavandula angustifolia',   'Ansiolítica,Sedante,Antifúngica,Cicatrizante,Analgésica',
     'El aceite esencial de lavanda puede aplicarse puro en pequeñas áreas.',
     'Reduce ansiedad e insomnio. Aplicada en piel acelera cicatrización de quemaduras leves.'),
    ('Romero',       'Salvia rosmarinus',        'Estimulante circulatorio,Antioxidante,Antibacteriano,Hepatoprotector,Nootrópico suave',
     'Contraindicado en embarazo en dosis altas. No usar en epilepsia.',
     'Mejora la memoria estimulando el flujo cerebral. En fricciones combate la alopecia androgénica.'),
    ('Curcuma',      'Curcuma longa',            'Antiinflamatoria potente,Antioxidante,Hepatoprotectora,Anticancerígena,Inmunomoduladora',
     'Absorción máxima combinada con pimienta negra y grasas saludables.',
     'La curcumina bloquea las mismas rutas inflamatorias que antiinflamatorios de síntesis.'),
    ('Jengibre',     'Zingiber officinale',      'Antiemético,Antiinflamatorio,Termogénico,Digestivo,Circulatorio',
     'En personas con anticoagulantes consultar al médico antes de usar en dosis altas.',
     'El antiemético más estudiado en náuseas del embarazo. Activa la circulación periférica.'),
    ('Eucalipto',    'Eucalyptus globulus',      'Expectorante,Antiséptico,Broncodilatador,Antibacteriano,Febrífugo',
     'No usar aceite esencial internamente. Evitar en niños menores de 6 años.',
     'El eucaliptol fluidifica el moco y dilata bronquios. Fundamental en gripe y bronquitis.'),
    ('Valeriana',    'Valeriana officinalis',    'Sedante,Ansiolítica,Antiespasmódica,Hipnótica,Miorelajante',
     'El efecto sedante se potencia con alcohol. Evitar conducir tras su consumo en dosis altas.',
     'Reduce la latencia del sueño sin generar dependencia. Ideal para insomnio de conciliación.'),
    ('Cola Caballo', 'Equisetum arvense',        'Diurética,Remineralizante,Cicatrizante,Antiinflamatoria,Hemostática',
     'No usar en insuficiencia renal. Tomar con abundante agua. Máximo 6 semanas continuas.',
     'Rica en sílice orgánico, refuerza huesos, uñas y cabello. Excelente diurético natural.'),
    ('Calendula',    'Calendula officinalis',    'Cicatrizante,Antiinflamatoria,Antifúngica,Emoliente,Antibacteriana',
     'Una de las plantas más seguras. Puede producir dermatitis en alérgicos a asteráceas.',
     'Acelera la cicatrización de heridas y quemaduras. Trata dermatitis atópica y eccemas.'),
    ('Tomillo',      'Thymus vulgaris',          'Antibacteriano,Expectorante,Antifúngico,Antioxidante,Antiviral',
     'Rico en hierro y vitamina C. En dosis altas puede irritar la mucosa digestiva.',
     'El timol es uno de los antisépticos naturales más potentes. Trata tos, bronquitis y laringitis.'),
    ('Pasiflora',    'Passiflora incarnata',     'Sedante,Ansiolítica,Antiespasmódica,Hipnótica,Analgésica',
     'Compatible con valeriana. Evitar combinación con benzodiacepinas.',
     'Actúa sobre los receptores GABA reduciendo ansiedad. Alivia palpitaciones de origen nervioso.'),
    ('Diente Leon',  'Taraxacum officinale',     'Diurético,Depurativo,Digestivo,Hepatoprotector,Prebiótico',
     'Recolectar solo en zonas limpias, ya que absorbe contaminantes del suelo.',
     'Estimula la producción de bilis. Depurativo hepático excepcional, rico en inulina y vitaminas.'),
    ('Boldo',        'Peumus boldus',            'Hepatoprotector,Colerético,Digestivo,Antioxidante,Laxante suave',
     'Contraindicado en obstrucción de vías biliares. No usar más de 4 semanas seguidas.',
     'La boldina estimula la secreción de bilis. El hepatoprotector más usado en Latinoamérica.'),
    ('Ortiga',       'Urtica dioica',            'Diurética,Antiinflamatoria,Remineralizante,Depurativa,Antihistamínica',
     'Cocida o seca pierde el poder urticante. Las semillas son adaptógenas y energizantes.',
     'Elimina el ácido úrico, aliada en gota y artritis. Extraordinariamente nutritiva.'),
    ('Salvia',       'Salvia officinalis',       'Antisudorífica,Antimicrobiana,Estrogénica leve,Digestiva,Neuroprotectora',
     'Evitar en embarazo y lactancia. No superar 15 g/día de hoja seca.',
     'La planta de la menopausia: reduce sofocos y sudoración nocturna. Antiséptico oral potente.'),
    ('Anis',         'Pimpinella anisum',        'Carminativo,Espasmolítico,Expectorante,Galactagogo,Estrogénico suave',
     'El aceite esencial puede ser tóxico en dosis altas. La infusión es segura.',
     'Alivia gases y cólicos intestinales. Estimula la producción de leche materna.'),
    ('Melisa',       'Melissa officinalis',      'Ansiolítica,Antiviral,Digestiva,Sedante,Antiespasmódica',
     'Combina perfecto con valeriana para el insomnio. Las hojas frescas conservan mejor el aroma.',
     'Combate ansiedad y taquicardias nerviosas. Antiviral demostrado contra herpes labial.'),
    ('Echinacea',    'Echinacea purpurea',       'Inmunoestimulante,Antiviral,Antibacteriana,Antiinflamatoria,Cicatrizante',
     'No usar más de 8 semanas continuas. No recomendada en enfermedades autoinmunes.',
     'Reduce duración e intensidad de resfríos. Estimula la producción de glóbulos blancos.'),
    ('Te Verde',     'Camellia sinensis',        'Antioxidante potente,Termogénico,Cardioprotector,Neuroprotector,Anticancerígeno',
     'Contiene cafeína. Evitar en embarazo e hipertiroidismo en dosis altas.',
     'Las catequinas (EGCG) neutralizan radicales libres. Protege el corazón reduciendo LDL oxidado.'),
    ('Ginkgo',       'Ginkgo biloba',            'Vasodilatador,Antioxidante,Neuroprotector,Anticoagulante suave,Nootrópico',
     'Interacción con anticoagulantes (warfarina, aspirina). Consultar al médico.',
     'Mejora la microcirculación cerebral aliviando tinnitus y mareos. El árbol más antiguo del mundo.'),
]

existing = conn.execute('SELECT COUNT(*) FROM base_conocimiento_salud').fetchone()[0]
if existing > 0:
    print(f'La base ya tiene {existing} hierbas. Nada que hacer.')
    conn.close()
    sys.exit(0)

conn.executemany(
    'INSERT INTO base_conocimiento_salud (nombre_remedio,planta_base,propiedades,contraindicaciones,dosificacion) VALUES (?,?,?,?,?)',
    hierbas
)
conn.commit()
count = conn.execute('SELECT COUNT(*) FROM base_conocimiento_salud').fetchone()[0]
print(f'Seed completado: {count} hierbas cargadas en {DB_PATH}')
conn.close()
