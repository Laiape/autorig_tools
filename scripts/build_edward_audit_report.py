"""Create the evidence-backed Spanish Edward PDF and embedded-data canvas.

Run after the final interactive receipts finish. No Maya import is required.
"""
from collections import Counter
from datetime import datetime
import html
import json
from pathlib import Path
import statistics

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.graphics.shapes import Drawing, Rect, String
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/full_audit_20261015_v001'
ROUTING=FOLDER.parent/'driver_routing_20261015_v001'
OUTPUT=ROOT/'output/pdf/edward-rig-audit.pdf'
CANVAS=Path('C:/Users/LaiaPeris/.cursor/projects/c-proyectos/canvases/edward-driver-routing.canvas.tsx')

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def num(value,digits=2):return ('%.*f'%(digits,value)).replace('.',',')
def mib(value):return num(value/1048576)
def kib(value):return num(value/1024,1)
def ms(value):return num(value,2)
def safe(text):return html.escape(str(text)).replace('\n','<br/>')

CAT=read(FOLDER/'catalog.json')
STORE=read(FOLDER/'storage.json')
EXTRA_MODEL=read(FOLDER/'model_storage_extra.json')['payloads']
SCALP=read(FOLDER/'scalp_payload.json')
PAYLOAD={r['label']:r for r in STORE['payloads']}
PROFILE_PREFIX='final2_profile_wrinkles' if (FOLDER/'final2_profile_wrinkles0.summary.json').exists() else 'final_profile_wrinkles'
PROFILES={w:read(FOLDER/('%s%d.summary.json'%(PROFILE_PREFIX,w))) for w in (0,1)}
NODE_CPU={w:{r['node']:r['inclusive_us']/48000 for r in p['node_cpu']} for w,p in PROFILES.items()}
PERF={p.stem.replace('.performance',''):read(p) for p in FOLDER.glob('*.performance.json') if 'timing' in read(p)}
OLD=[dict(read(p),file=p.name) for p in sorted(ROUTING.glob('*_C_r1.performance.json'))]
ROUTES=[p for k,p in PERF.items() if k.startswith('final_routing_')]
ROUTES.sort(key=lambda r:r['label'])
GPU_QUALITY=[read(p) for p in sorted(FOLDER.glob('final_gpu_quality_*.json'))]
RESOLUTION=read(FOLDER/'final_quality_resolution.json')['candidates'] if (FOLDER/'final_quality_resolution.json').exists() else []
LABELS={'original':'Original','direct':'Directa','shared':'Driver cuerpo + cara',
        'shared_wrinkles':'Drivers + salida wrinkles','body_driver':'Solo driver cuerpo','face_driver':'Solo driver facial'}

def component(name):
    for prefix in ('final2_component_','final_component_'):
        if prefix+name in PERF:return PERF[prefix+name]
    return None

def references(prefix):
    return [p for k,p in PERF.items() if k.startswith(prefix+'reference')]

def delta(name):
    row=component(name)
    if not row:return 'Sin ablación'
    prefix=row['label'].split(name)[0]
    refs=references(prefix)
    if not refs:return '-'
    baseline=statistics.median(r['timing']['median_ms'] for r in refs)
    diff=baseline-row['timing']['median_ms']
    span=max(r['timing']['median_ms'] for r in refs)-min(r['timing']['median_ms'] for r in refs)
    noise=max(span,baseline*.05)
    return ('%s ms%s'%(num(diff), ' *' if abs(diff)<=noise else ''))

DATA={
    'scene_bytes':CAT['scene_bytes'], 'node_count':len(CAT['nodes']),
    'modules':[], 'layers':[], 'components':[], 'routes':[],
    'storage':[{k:r[k] for k in ('label','kind','nodes','bytes')} for r in STORE['payloads']],
    'state_tests':[], 'display_tests':[],
    'gpu_quality':GPU_QUALITY,'quality_resolution':RESOLUTION,
    'model_extras':EXTRA_MODEL,'scalp':SCALP,
    'variant_files':[dict(variant=v,file='Edward_'+('baseline' if v=='original' else v)+'.mb',
                          bytes=(ROUTING/('Edward_'+('baseline' if v=='original' else v)+'.mb')).stat().st_size)
                     for v in ('original','direct','body_driver','face_driver','shared','shared_wrinkles')],
}
for name,m in CAT['modules'].items():
    cpu={w:next(r for r in PROFILES[w]['modules'] if r['module']==name) for w in (0,1)}
    DATA['modules'].append(dict(name=name,nodes=len(m['exclusive_nodes']),bytes=PAYLOAD['module_'+name]['bytes'],
                                cpu_off=cpu[0]['cpu_inclusive_ms_per_frame'],cpu_on=cpu[1]['cpu_inclusive_ms_per_frame']))
for s in CAT['skins']:
    if any('|cabeza_high|' in g['shape'] or '|cabeza_low|' in g['shape'] for g in s['geometry']):
        g=s['geometry'][0]
        DATA['layers'].append(dict(name=s['name'],resolution='High' if '|cabeza_high|' in g['shape'] else 'Low',
                                  vertices=g['components'],influences=s['influences'],actual_max=g['maximum_actual_influences'],
                                  weights=g['nonzero_weights'],bytes=PAYLOAD['skin_'+s['name']]['bytes'],
                                  median=component('skin_'+s['name'])['timing']['median_ms'] if component('skin_'+s['name']) else None,
                                  delta=delta('skin_'+s['name'])))
for k,p in PERF.items():
    if k.startswith(('final_component_','final2_component_')):
        DATA['components'].append(dict(label=k,median=p['timing']['median_ms'],p95=p['timing']['p95_ms'],
                                       cv=p['timing']['cv_percent'],runs=[r['median_ms'] for r in p['runs']]))
    if k.startswith('final_states_'):DATA['state_tests'].append(dict(label=k,state=p['state'],**p['timing']))
    if k.startswith('final_display_'):DATA['display_tests'].append(dict(label=k,**p['timing']))
DATA['hybrid_tests']=[dict(label=p['label'],**p['timing']) for k,p in PERF.items() if k.startswith('final_hybrid_')]
for p in ROUTES:
    DATA['routes'].append(dict(variant=p['variant'],wrinkles=p['wrinkles'],label=p['label'],
                              median=p['timing']['median_ms'],p95=p['timing']['p95_ms'],
                              cv=p['timing']['cv_percent'],runs=[r['median_ms'] for r in p['runs']]))

INK=colors.HexColor('#182C38');ACCENT=colors.HexColor('#156F78');MUTED=colors.HexColor('#536773')
LIGHT=colors.HexColor('#EDF3F4');RULE=colors.HexColor('#D8E2E5')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleEdward',fontName='Helvetica-Bold',fontSize=26,leading=30,textColor=INK,spaceAfter=12))
styles.add(ParagraphStyle(name='SectionEdward',fontName='Helvetica-Bold',fontSize=17,leading=21,textColor=INK,spaceAfter=10,keepWithNext=True))
styles.add(ParagraphStyle(name='SubEdward',fontName='Helvetica-Bold',fontSize=11,leading=15,textColor=ACCENT,spaceBefore=10,spaceAfter=5,keepWithNext=True))
styles.add(ParagraphStyle(name='BodyEdward',fontName='Helvetica',fontSize=9.2,leading=13.3,textColor=INK,spaceAfter=7))
styles.add(ParagraphStyle(name='SmallEdward',fontName='Helvetica',fontSize=7.7,leading=10.5,textColor=MUTED,spaceAfter=6))
styles.add(ParagraphStyle(name='CellEdward',fontName='Helvetica',fontSize=7.5,leading=10,textColor=INK,wordWrap='CJK'))
styles.add(ParagraphStyle(name='HeadEdward',fontName='Helvetica-Bold',fontSize=7.7,leading=10,textColor=colors.white))
story=[]
def para(text,style='BodyEdward'):
    story.append(Paragraph(text,styles[style]))
def title(text,tag=None):
    if story:story.append(PageBreak())
    if tag:para(tag.upper(),'SmallEdward')
    para(text,'SectionEdward')
def sub(text):para(text,'SubEdward')
def table(headers,rows,widths=None):
    cells=[[Paragraph(safe(v),styles['HeadEdward']) for v in headers]]
    cells += [[Paragraph(safe(v),styles['CellEdward']) for v in row] for row in rows]
    t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),ACCENT),('VALIGN',(0,0),(-1,-1),'TOP'),
                           ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
                           ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
                           ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),
                           ('LINEBELOW',(0,-1),(-1,-1),.5,RULE)]))
    story.append(t);story.append(Spacer(1,8))

def bar_chart(rows,label='Milisegundos por fotograma, mediana; menor es mejor'):
    if not rows:return
    width=500;left=185;right=55;top=20;step=24;maximum=max(v for _,v in rows)*1.08
    d=Drawing(width,top+step*len(rows)+24)
    for i,(name,value) in enumerate(rows):
        y=24+(len(rows)-i-1)*step
        d.add(String(0,y+3,name,fontName='Helvetica',fontSize=8,fillColor=INK))
        d.add(Rect(left,y,(width-left-right)*value/maximum,13,fillColor=ACCENT,strokeColor=None))
        d.add(String(width-right+5,y+3,num(value),fontName='Helvetica-Bold',fontSize=8,fillColor=INK))
    d.add(String(left,3,label,fontName='Helvetica',fontSize=7,fillColor=MUTED))
    story.append(d);story.append(Spacer(1,8))

def timing_rows(rows):
    return [[r['label'],ms(r['timing']['median_ms']),ms(r['timing']['p95_ms']),
             ' / '.join(ms(v['median_ms']) for v in r['runs'])] for r in rows]

def footer(canvas,doc):
    canvas.saveState();w,h=A4
    canvas.setStrokeColor(RULE);canvas.line(18*mm,17*mm,w-18*mm,17*mm)
    canvas.setFillColor(MUTED);canvas.setFont('Helvetica',7)
    canvas.drawString(18*mm,12*mm,'EDWARD / Auditoría de rig / 15 octubre 2026')
    canvas.drawRightString(w-18*mm,12*mm,str(doc.page))
    canvas.restoreState()

# Executive result, intentionally based only on completed captures.
para('EDWARD','SmallEdward')
para('Rendimiento, peso<br/>y opciones de mejora','TitleEdward')
para('Informe de mediciones del rig - Maya 2026.3.3 - 15 de octubre de 2026','SmallEdward')
final_on=[r for r in DATA['routes'] if r['wrinkles'] and r['variant']!='original']
if final_on:
    grouped={v:statistics.median(r['median'] for r in final_on if r['variant']==v) for v in {r['variant'] for r in final_on}}
    best=min(grouped,key=grouped.get)
    repeat_spans=[max(r['median'] for r in final_on if r['variant']==v)-min(r['median'] for r in final_on if r['variant']==v)
                  for v in grouped if sum(r['variant']==v for r in final_on)>1]
    decision_band=max([grouped[best]*.05]+repeat_spans)
    ties=[v for v,value in grouped.items() if value-grouped[best]<=decision_band]
    decision=('La ruta directa queda dentro de la variación de la mejor y evita añadir una malla facial o de salida: es la opción preferible por sencillez con estos datos.'
              if 'direct' in ties else 'La menor mediana observada corresponde a '+LABELS[best]+'. Adoptarla requiere considerar la variación y la puerta de calidad del alcance probado.')
    DATA['decision']=dict(best_observed=best,wrinkles_on_medians=grouped,comparison_band_ms=decision_band,indistinguishable_within_band=ties,recommendation=decision)
    para('<b>Resultado de la tanda final:</b> con wrinkles, la menor mediana entre los prototipos fue '+safe(LABELS[best])+
         ' ('+ms(grouped[best])+' ms/fotograma). La tabla de pasadas y las repeticiones permiten valorar su estabilidad.')
    para('<b>Recomendación sobre mallas:</b> '+safe(decision))
    if any(not q['accepted'] for q in GPU_QUALITY):
        b=PERF['final_states_B']['timing']['median_ms']
        para('<b>Calidad antes que velocidad:</b> GPU difiere de Parallel CPU en collar3 (hasta 0,136349 unidades) y collar2 (0,000709). '+
             'La referencia conservadora de animación es Parallel CPU, sin wrinkles: '+ms(b)+' ms/fotograma. '+
             'Los tiempos GPU de drivers describen rendimiento, pero no certifican calidad completa.')
    normal_cache=[r for r in RESOLUTION if r['state']=='D' and not r['blocked_collars']]
    if len(normal_cache)==2 and all(r['accepted'] for r in normal_cache):
        off=PERF['final_states_D']['timing']['median_ms'];on=PERF['final_states_wrinkles1_D']['timing']['median_ms']
        para('<b>Reproducción ya cacheada:</b> '+ms(off)+' ms sin wrinkles y '+ms(on)+' ms con wrinkles; error 0 frente a CPU en los 11 saltos y 2 ediciones probados. '+
             'Este resultado corresponde a caché caliente; no equivale a recalcular una pose desde cero.')
else:raise RuntimeError('Final routing comparison must finish before report generation.')
ref=component('reference_start');prx=component('all_PRX');skin=component('all_skinning')
if ref and prx and skin:
    para('El puenteo diagnóstico de todos los PRX obtuvo '+ms(prx['timing']['median_ms'])+' ms y el de todo el skinning '+
         ms(skin['timing']['median_ms'])+' ms, frente a '+ms(ref['timing']['median_ms'])+' ms de la referencia de su cohorte. '+
         'Estas pruebas eliminan deformación y sirven para localizar costes; no son versiones finales utilizables.')
table(['Dato medido','Resultado'],[
    ['Escena nativa de referencia',mib(CAT['scene_bytes'])+' MiB ('+str(CAT['scene_bytes'])+' bytes)'],
    ['Inventario',str(len(CAT['nodes']))+' nodos; 18 módulos; 58 skins; 23 PRX; 9 blendShapes'],
    ['Modelo: todas las salidas poligonales sin historial',mib(PAYLOAD['model_all_display_outputs']['bytes'])+' MiB'],
    ['XGen: 8 nodos y datos nativos aislados',mib(next(r['bytes'] for r in EXTRA_MODEL if r['label']=='xgen_nodes'))+' MiB; no aditivo a otras exportaciones'],
    ['58 skinClusters: datos nativos aislados',mib(PAYLOAD['all_skinClusters']['bytes'])+' MiB'],
    ['3 blendShapes de correctivas: datos aislados',mib(PAYLOAD['all_corrective_blendShapes']['bytes'])+' MiB'],
    ['Wrinkles: 6 nodos y datos nativos',mib(PAYLOAD['wrinkles']['bytes'])+' MiB'],
    ['23 PRX: parámetros serializados',kib(PAYLOAD['all_PRX']['bytes'])+' KiB; excluye cachés de ejecución'],
],[255,255])
sub('Decisiones que se pueden tomar con estas pruebas')
para('1. Para posing conservador, Parallel CPU y sin wrinkles; para reproducir la animación ya calculada, la caché caliente supera la puerta contra CPU en el alcance probado.<br/>'
     '2. Usar la comparación final para escoger la ruta de drivers; una malla intermedia no garantiza acelerar todos los casos.<br/>'
     '3. Conservar el low res si aporta un LOD útil: ocupa disco, pero ocultarlo y quitarle sus skins no han demostrado por sí solos una mejora relevante en todas las tandas.<br/>'
     '4. Priorizar los nodos de los módulos que concentran CPU y los PRX con datos del Profiler antes de rehacer el rig.')
para('<b>Estado de entrega:</b> las modificaciones están en copias de experimento. La escena artística original no se ha sobrescrito. '+
     'Los prototipos nuevos cambian qué recibe las correctivas corporales; esa diferencia artística requiere revisar la forma del cuerpo y la ropa.','SmallEdward')

title('Qué se ha medido y cómo','Lectura de las cifras')
para('Se distinguen tres magnitudes que no son intercambiables: <b>tamaño nativo en disco</b> (MiB/KiB); '+
     '<b>tiempo de pared por fotograma</b> (currentTime + refresh forzado de Viewport 2.0); y '+
     '<b>tiempo CPU inclusivo por nodo</b> del Profiler. Las duraciones CPU pueden solaparse en paralelo y anidarse. '+
     'No son el ahorro que se obtendría al borrar un módulo ni pueden sumarse para calcular FPS.')
table(['Protocolo','Condición'],[
    ['Equipo','Intel Core i9-14900HX, 32 procesadores lógicos; 32 GB RAM; NVIDIA RTX 5060 Laptop, 8 GB; OpenGL 4.6'],
    ['Aplicación','Maya 2026 / API '+str(read(FOLDER/'final_environment.json')['api'])+'; sesión interactiva VP2; texturas desactivadas'],
    ['Workload final','18 módulos, 10 poses, controles de ambos lados, cara, cuello, dedos, dientes y lengua. Curvas nativas lineales entre fotogramas 1-48. FK activado en miembros.'],
    ['Cada prueba temporal','1 pasada completa de calentamiento + 3 pasadas medidas. Se descartan 8 fotogramas de cada pasada; quedan 120 muestras.'],
    ['Cronómetro','Incluye evaluación y refresco/envío al visor. No es tiempo aislado de GPU ni reproducción libre sin límite. FPS derivados = 1000 / mediana.'],
    ['Diagnóstico','Lectura de vértices, capturas del Profiler e inventario de GPU fuera de las muestras temporizadas.'],
    ['Calidad','Tolerancia 0,0001 unidades de escena, puntos evaluados en espacio mundo, ida y vuelta de poses. Se preservan pesos y targets.'],
    ['Comparabilidad','R1: 15 poses y sesión inicial. F1: nueva sesión, inventario de paneles 657 x 397; conserva valores estáticos del snapshot. F2: una perspectiva 1317 x 754, neutral y 4 selectores FK=1 comprobados; 34 canales animados. Comparar únicamente dentro de una cohorte.'],
],[130,380])
sub('Cómo se interpreta el peso')
para('Las exportaciones estrictas incluyen solo los nodos seleccionados. Los módulos se asignan al grupo más específico; por ejemplo, '+
     'los nodos de cara anidados bajo cuello no se contabilizan otra vez como cuello. Las utilidades compartidas se muestran aparte. '+
     'Los archivos aislados contienen cabeceras y omiten conexiones externas; no son rigs funcionales independientes. Su suma no reconstruye exactamente el tamaño de la escena completa.')
para('La atribución final incluye curvas SDK nativas que alimentan nodos propios de un módulo; detiene el recorrido en time y en DAG ajeno o deformadores. '+
     'Se volvió a exportar el payload de los 18 módulos tras refinar este criterio. El inventario previo se conserva como evidencia, pero no se usa para la tabla final.','SmallEdward')
para('El payload de pesos no nulos (8 bytes por double) y el de puntos son indicadores de datos. No miden el almacenamiento interno de Maya ni VRAM. '+
     'La memoria del proceso después del inventario fue '+mib(CAT['memory']['working_set_bytes'])+' MiB de conjunto de trabajo y '+
     mib(CAT['memory']['private_bytes'])+' MiB privados, incluyendo Maya, plugins, arrays temporales y cachés. No se asigna ficticiamente RAM a cada módulo.')
para('Fuentes metodológicas: <link href="https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/file.html" color="#156F78">Autodesk file / exportSelectedStrict</link>; '+
     '<link href="https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/profiler.html" color="#156F78">Autodesk Profiler</link>.','SmallEdward')

title('Modelo y coste de visualización','Geometría')
model=[m for m in CAT['meshes'] if '|geo_GRP|' in m['path'] and not m['intermediate']]
para('El catálogo contiene '+str(len(CAT['meshes']))+' shapes de malla contando originales/intermedios. En geo_GRP hay '+
     str(len(model))+' salidas no intermedias, con '+str(sum(m['vertices'] for m in model))+' vértices y '+str(sum(m['polygons'] for m in model))+' polígonos. '+
     'No se suman las mallas originales de historial como si fueran geometría visible adicional.')
table(['Malla / conjunto','Vértices','Polígonos','Payload baked MiB'],[
    [name,str(next(m['vertices'] for m in model if m['name'].startswith(name+'_'))),str(next(m['polygons'] for m in model if m['name'].startswith(name+'_'))),
     mib(PAYLOAD['model_'+name]['bytes'])] for name in ('cabello_geo','cabeza_high','cabeza_low','cuerpo_base')]+[
    ['Todas las salidas, visibles y ocultas',str(sum(m['vertices'] for m in model)),str(sum(m['polygons'] for m in model)),mib(PAYLOAD['model_all_display_outputs']['bytes'])],
    ['Solo salidas visibles',str(sum(m['vertices'] for m in model if m['visible'])),str(sum(m['polygons'] for m in model if m['visible'])),mib(PAYLOAD['model_visible_outputs']['bytes'])],
],[180,90,95,145])
display=[p for k,p in PERF.items() if k.startswith('final_display_')]
display.sort(key=lambda p:p['label'])
if display:
    sub('Pruebas de LOD y dibujo en la misma escena')
    table(['Prueba','Mediana ms','p95 ms','Pasadas ms'],timing_rows(display),[220,65,65,160])
    para('Ocultar el pelo puede podar también su rama de skinning. Ocultar curvas mediante el visor incluye controles y curvas de construcción. '+
         'Estas pruebas no separan milisegundos de rasterización de los de evaluación. El modo low puede conservar la cabeza high activa como driver de los collares.','SmallEdward')
title('Datos de pelo, XGen y materiales','Modelo / datos nativos adicionales')
table(['Datos adicionales del modelo','Nodos','MiB nativos aislados'],[
    [r['label'],r['nodes'],mib(r['bytes'])] for r in EXTRA_MODEL]+[
    ['Curvas importadas de puntos del scalp',SCALP['curves'],mib(SCALP['bytes'])]
],[310,70,130])
para('XGen representa un volumen de datos importante: '+mib(next(r['bytes'] for r in EXTRA_MODEL if r['label']=='xgen_nodes'))+
     ' MiB en su exportación aislada. Las mallas almacenadas, incluyendo originales de historial, ocupan '+
     mib(next(r['bytes'] for r in EXTRA_MODEL if r['label']=='stored_polygon_meshes'))+' MiB en otra exportación. '+
     'Estas cifras pueden solaparse; no se suman como porcentajes del .mb de referencia. El modelo baked mide otra cosa: salidas evaluadas sin historial.')
para('Hay 5.451 animCurveTL importadas conectadas a los tres componentes pnts de los 1.817 vértices de scalp_cabello_Shape. '+
     'Cada una tiene una clave y no se encontraron conexiones de entrada; su payload conjunto es '+mib(SCALP['bytes'])+' MiB. '+
     'No se atribuyen como SDK de los módulos. No aparecieron eventos EvaluateNode de esas curvas en las capturas, por lo que no se presenta quitarlas como una ganancia de FPS.')
para('Hay '+str(len(STORE['textures']))+' nodos file y 4 descripciones XGen. Las rutas externas se enumeran en storage.json. '+
     'Varias son relativas y otras apuntan a E:/ANIMUM; el inventario inicial no las resolvía contra el workspace. '+
     'No se inventa su peso ni se considera que forman parte de los 163,47 MiB del archivo .mb. Las pruebas temporales usan texturas desactivadas, por lo que no caracterizan el coste de sombreado final.')
para('El pelo poligonal es la malla individual más grande de las cuatro exportadas. Un LOD específico de pelo y ropa es una opción de producción; '+
     'su beneficio debe contrastarse con la tabla de visibilidad y revisarse visualmente. No se ha decimado ni alterado el modelo artístico.')

title('Desglose de los 18 módulos','Nodos nativos y CPU inclusiva')
table(['Módulo','Nodos propios','KiB nativos','CPU off ms/f','CPU on ms/f'],[
    [r['name'],r['nodes'],kib(r['bytes']),num(r['cpu_off'],3),num(r['cpu_on'],3)] for r in DATA['modules']],
    [150,80,90,95,95])
para('CPU off/on = suma de eventos EvaluateNode inclusivos de los nodos exclusivos / 48 fotogramas, con wrinkles puenteados o activos (F2, FK y perspectiva fijados). '+
     'Es una atribución de trabajo CPU de diagnóstico; los nodos agrupados en GPU y las duraciones anidadas impiden convertirla directamente en ahorro o FPS. '+
     'La diferencia entre off y on de un módulo puede reflejar planificación y ruido de la captura.','SmallEdward')
table(['Fuera de los módulos exclusivos','CPU off ms/f','CPU on ms/f'],[
    ['Utilidades compartidas',num(PROFILES[0]['shared']['cpu_inclusive_ms_per_frame'],3),num(PROFILES[1]['shared']['cpu_inclusive_ms_per_frame'],3)],
    ['Globales, deformadores y nodos fuera del catálogo de módulos',num(PROFILES[0]['outside_modules']['cpu_inclusive_ms_per_frame'],3),num(PROFILES[1]['outside_modules']['cpu_inclusive_ms_per_frame'],3)],
    ['Todos los eventos EvaluateNode, referencia de CPU inclusiva',num(PROFILES[0]['all_evaluate_node_cpu_ms_per_frame'],3),num(PROFILES[1]['all_evaluate_node_cpu_ms_per_frame'],3)],
],[310,100,100])
largest=sorted(DATA['modules'],key=lambda r:r['cpu_off'],reverse=True)[:3]
para('Prioridad de inspección CPU en esta captura: '+', '.join(r['name']+' ('+num(r['cpu_off'],3)+' ms inclusivos/f)' for r in largest)+'. '+
     'El archivo summary conserva los nodos más costosos de cada módulo para poder localizar el cálculo, no solo contar nodos.')
para('La ablación masiva por frozen de mandíbula bloqueó la preparación y se canceló recuperando el snapshot. No se asigna un tiempo por eliminación a ese módulo. '+
     'Los 18 módulos tienen datos nativos y eventos CPU; la comparación no depende de esa prueba fallida.','SmallEdward')

title('Skinning y capas faciales','Qué añade el high y qué añade el low')
table(['Capa facial','Res.','Infl.','Pesos no cero','KiB','Ahorro al puentear'],[
    [r['name'],r['resolution'],str(r['influences'])+' / máx '+str(r['actual_max']),r['weights'],kib(r['bytes']),r['delta']]
    for r in DATA['layers']], [170,35,65,78,55,107])
para('Infl. = número de influencias conectadas / máximo real por vértice. High: 11.475 vértices por capa, 8 skinClusters y 144.531 pesos no nulos. '+
     'Low: 3.082 vértices por capa, 4 skinClusters y 19.617 pesos no nulos. Las capas operan secuencialmente; compartir la misma malla no las convierte en una única deformación.','SmallEdward')
low=[r for r in DATA['layers'] if r['resolution']=='Low'];high=[r for r in DATA['layers'] if r['resolution']=='High']
lowbls=PAYLOAD['blend_cabeza_low_poseCorrectives_BLS']['bytes']
para('<b>¿Pesa más tener skinning también en low res?</b> Sí, en datos: sus cuatro payloads de skin suman '+
     kib(sum(r['bytes'] for r in low))+' KiB, además de '+mib(PAYLOAD['model_cabeza_low']['bytes'])+
     ' MiB de geometría baked y '+kib(lowbls)+' KiB del blendShape low. Estas exportaciones aisladas no son un delta exacto del archivo completo. '+
     'En ejecución, la rama oculta puede ser podada: el ahorro medido al puentear sus cuatro skins fue '+delta('all_facial_low_skinning')+'.')
table(['Grupo desactivado','Mediana ms/f','p95 ms/f','Ahorro frente a referencias'],[
    [name,ms(component(key)['timing']['median_ms']),ms(component(key)['timing']['p95_ms']),delta(key)]
    for name,key in [('Todo el skinning','all_skinning'),('8 capas faciales high','all_facial_high_skinning'),('4 capas faciales low','all_facial_low_skinning')]
    if component(key)],[190,90,90,140])
para('* Diferencia dentro del mayor entre el rango de las referencias de esa cohorte y el 5% de su mediana: no demuestra un ahorro estable. '+
     'Los deltas son marginales y no aditivos. Puentear un skin cambia la pose recibida por sistemas posteriores, por lo que tampoco representa el coste aislado de su algoritmo.','SmallEdward')
para('Solución con menor riesgo: conservar el low res como LOD y comprobar la poda real con sus eventos. Si se crea un paquete high-only para render, '+
     'retirar solo low y sus deformadores propios en una copia; no retirar articulaciones compartidas. No se ha aplicado esa eliminación al rig original.')
para('Densidad destacada: C_mouth_local_SKC conecta 103 influencias, con máximo real 27 y media 2,75 por vértice; '+
     'skinCluster41 del low llega a máximo 33 y media 2,33. Esto identifica vértices que conviene revisar si se estudia simplificar pesos; '+
     'podar a 4 u 8 influencias modificaría la deformación y necesita una validación específica. No se ha realizado esa poda.','SmallEdward')
para('El conteo de pesos considera cualquier valor estrictamente distinto de cero; puede incluir residuos muy pequeños. '+
     'maxInfluences=5 y maintainMaxInfluences=True constan en boca high y en skinCluster41, pero el inventario de pesos almacenados supera ese número. '+
     'No se infiere la importancia visual de esas influencias solo por contarlas.','SmallEdward')
if (FOLDER/'final_weight_thresholds.json').exists():
    thresholds={r['skin']:r for r in read(FOLDER/'final_weight_thresholds.json')}
    for skin_name in ('C_mouth_local_SKC','skinCluster41'):
        r=thresholds[skin_name]
        para(safe(skin_name)+': máximo de influencias con |peso| > 0,000001: '+str(next(t['maximum_per_vertex'] for t in r['thresholds'] if t['threshold']==1e-6))+
             '; con |peso| > 0,001: '+str(next(t['maximum_per_vertex'] for t in r['thresholds'] if t['threshold']==1e-3))+'.','SmallEdward')

# Complete skin inventory in three bounded pages.
skins=sorted(CAT['skins'],key=lambda s:PAYLOAD['skin_'+s['name']]['bytes'],reverse=True)
for start in range(0,len(skins),20):
    title('Inventario completo de skinClusters','Apéndice de skinning / '+str(start+1)+'-'+str(min(start+20,len(skins))))
    rows=[]
    for s in skins[start:start+20]:
        geos=s['geometry'];g=geos[0] if geos else {}
        shape=g.get('shape','').rsplit('|',1)[-1]
        rows.append([s['name'],shape,s['influences'],g.get('maximum_actual_influences','-'),g.get('nonzero_weights','-'),
                     kib(PAYLOAD['skin_'+s['name']]['bytes']),num(NODE_CPU[0].get(s['name'],0),3)])
    table(['SkinCluster','Salida','Infl.','Máx/v','Pesos','KiB','CPU ms/f'],rows,[145,120,35,35,65,55,55])
    para('CPU = EvaluateNode inclusivo / 48 fotogramas de la captura OFF. Un valor 0 puede significar poda o agrupación en GPU: no prueba coste cero. '+
         'DQ está activo en las capas high de cejas y párpados. Los ajustes, pesos reales, geometrías y payloads densos están en catalog.json. '+
         'Los datos de los 58 skins se extrajeron sin errores, exponiendo temporalmente la entrada primaria antes de Bifrost.','SmallEdward')

title('Proximity Wrap: 23 deformadores','PRX')
prxrows=[]
for n,p in CAT['prx'].items():
    r=component('prx_'+n)
    drivers=len(p.get('drivers',{}))
    prxrows.append([n,drivers,kib(PAYLOAD['prx_'+n]['bytes']),num(NODE_CPU[0].get(n,0),3),
                    ms(r['timing']['median_ms']) if r else '-',delta('prx_'+n)])
table(['PRX','Drivers','KiB','CPU ms/f','Sin él ms/f','Ahorro ms/f'],prxrows,[145,45,55,75,80,110])
para('El conjunto contiene 29 entradas: 14 de cuerpo, 2 de cabeza, 9 de pantalón y 4 de otra superficie. '+
     'Los PRX guardan pocos parámetros nativos ('+kib(PAYLOAD['all_PRX']['bytes'])+' KiB entre los 23), pero dependen de geometrías de reposo, drivers y datos preparados en ejecución. '+
     'Un archivo pequeño no implica un deformador barato.','SmallEdward')
if component('all_PRX'):
    para('Puentear todos los PRX: '+ms(component('all_PRX')['timing']['median_ms'])+' ms/fotograma; diferencia marginal frente a referencias: '+delta('all_PRX')+'. '+
         'El resultado sirve para priorizar la ropa y los drivers. Eliminar PRX deja prendas sin la deformación esperada y no es una solución equivalente.')
para('Optimización propuesta: reducir complejidad de driver solo después de validar ropa y collares en las poses extremas. '+
     'Las entradas con distinta topología conservan sus fuentes; no se ha conectado el pantalón ni otra superficie arbitrariamente a la malla del cuerpo.')

title('Correctivas y rutas de geometría','BlendShapes')
table(['BlendShape','Targets','Puntos guardados','KiB nativos','CPU off ms/f'],[
    [b['name'],len(b['targets']),sum(t['stored_points'] for t in b['targets']),kib(PAYLOAD['blend_'+b['name']]['bytes']),
     num(NODE_CPU[0].get(b['name'],0),3)] for b in CAT['blendShapes']], [210,50,90,80,80])
para('Hay 3 blendShapes de correctivas poligonales y 6 de construcción de parpadeo sobre curvas. '+
     'Estos últimos no son seis bibliotecas extra de correctivas faciales; sus targets incluyen geometría de curva conectada. '+
     'El peso total aislado de las 3 correctivas es '+mib(PAYLOAD['all_corrective_blendShapes']['bytes'])+' MiB.')
table(['Prueba','Mediana ms/f','Diferencia marginal'],[
    [label,ms(component(key)['timing']['median_ms']),delta(key)] for label,key in
    [('Puentear 3 correctivas','all_correctives'),('Puentear 6 blendShapes de párpados','eyelid_curve_blendShapes')]
    if component(key)],[280,100,130])
sub('La diferencia artística del cuerpo')
para('En la escena original: skin de cuerpo -> cuerpo visible -> correctivas -> driver oculto -> cinturon3_PRX. '+
     'Los otros 13 drivers corporales de PRX reciben el cuerpo visible anterior a esas correctivas. '+
     'Los 4 targets corporales tienen peso 1 y no reciben conexiones de peso. El cuerpo visible original coincide exactamente con la salida raw del skin.')
para('En los prototipos nuevos: skin -> correctivas -> cuerpo final, y las 14 entradas corporales comparten esa geometría corregida, por ruta directa o por driver. '+
     '<b>Esto cambia el resultado respecto al original:</b> máximo 1,827831 unidades en cuerpo y hasta aproximadamente 1,19 en algunas prendas; el cinturón conserva su resultado. '+
     'Puede tratarse de una intención de ajuste de ropa en el rig original. El informe no lo declara un error artístico ni aplica el cambio a producción.')
para('Las variantes nuevas sí son equivalentes entre ellas dentro de las poses verificadas: se comparan contra Directa. '+
     'La cara corregida puede pasar por cabeza_high_poseCorrectives_BLS_driver hacia wrinkles, cabeza final y conversión a mundo de collares. '+
     'La opción de salida wrinkles añade cabeza_high_wrinkles_driver después del conversor Bifrost.')

title('Comparación final de drivers','Mismo workload, una perspectiva')
table(['Variante / captura','Wrinkles','Mediana ms/f','p95 ms/f','Pasadas ms'],[
    [LABELS[r['variant']]+' / '+r['label'].split('_')[2], 'ON' if r['wrinkles'] else 'OFF',ms(r['median']),ms(r['p95']),
     ' / '.join(ms(v) for v in r['runs'])] for r in DATA['routes']], [180,50,80,80,120])
para('Las capturas de Directa y driver facial con wrinkles se repiten al final para comprobar el efecto del orden. '+
     'La escena Original es un resultado artístico distinto de los prototipos corporales, por lo que se incluye como referencia de uso y no como verificación de equivalencia.','SmallEdward')
if final_on:
    bar_chart([(LABELS[v]+' / wrinkles ON',value) for v,value in sorted(grouped.items(),key=lambda p:p[1])])
sub('Cómo escoger la variante')
para('<b>Decisión de esta tanda:</b> '+safe(decision)+' Se usa una banda descriptiva de '+ms(decision_band)+
     ' ms (mayor entre el 5% del mejor y la deriva observada en repeticiones). No es un intervalo de confianza estadístico. '+
     'Dentro de ella quedan: '+', '.join(LABELS[v] for v in ties)+'.')
para('Comparar primero calidad, después mediana y p95, y por último consistencia entre pasadas y repeticiones. '+
     'Una ventaja pequeña dentro de la deriva de referencias no justifica añadir complejidad. Con wrinkles, el coste del grafo y la transferencia de geometría puede dominar. '+
     'El driver facial y la malla de salida wrinkles son opciones independientes, no una garantía de ahorro universal.')

title('Peso de las variantes completas','Snapshots nativos de comparación')
table(['Variante','Archivo guardado','Bytes','MiB'],[
    [LABELS[r['variant']],r['file'],r['bytes'],mib(r['bytes'])] for r in DATA['variant_files']],[145,180,105,80])
para('Estos son tamaños reales de las copias completas guardadas. Incluyen datos y estado serializado de cada snapshot. '+
     'No se deben interpretar diferencias de archivo como RAM exacta ni como coste exclusivo de una nueva malla. '+
     'Al desconectar un driver pueden quedar datos de malla materializados sin conexión, y el estado guardado puede diferir aunque la geometría final coincida.')
sub('Qué sale de cada driver')
table(['Variante','Ruta corporal','Ruta facial'],[
    ['Original','Cuerpo raw visible; correctivas solo hacia driver y cinturón.','Correctivas -> grafo wrinkles -> conversor -> cabeza final.'],
    ['Directa','Correctivas -> cuerpo final -> 14 entradas corporales PRX.','Salida primaria directa a grafo/convertidor o final OFF.'],
    ['Solo driver cuerpo','Correctivas -> driver corporal existente -> 14 entradas PRX; cuerpo final corregido.','Como Directa.'],
    ['Solo driver facial','Como Directa.','Correctivas -> nueva malla driver -> grafo, collares y final OFF.'],
    ['Driver cuerpo + cara','Usa driver corporal.','Usa driver facial.'],
    ['Drivers + salida wrinkles','Usa driver corporal.','Además, conversor -> malla oculta de wrinkles -> cabeza final.'],
],[115,195,200])
para('Las 9 entradas de pantalón y 4 de otra superficie conservan sus drivers específicos. Las 2 entradas de cabeza conservan su conversión a mundo pre-wrinkles. '+
     'Los pesos, targets y vínculos nativos se conservan en las copias. La escena original no se sustituye por un prototipo.')

title('Primera tanda y respuesta al cambiar poses','Contexto R1')
table(['Variante','Wrinkles','Mediana ms/f','p95 ms/f','Pose completa ms'],[
    [LABELS[p['routing_variant']],'ON' if p['wrinkles_enabled'] else 'OFF',ms(p['timing']['median_ms']),ms(p['timing']['p95_ms']),
     ms(p['control_interaction']['timing']['median_ms']) if p.get('control_interaction',{}).get('timing') else '-'] for p in OLD],
    [180,60,90,90,90])
para('R1 usó 15 poses y visor 1170 x 793. El tiempo de pose aplica todos los canales de una pose y refresca; incluye llamadas de comandos. '+
     'No representa arrastrar un control con el ratón y no puede convertirse en FPS. Solo se midió en las tres primeras variantes.','SmallEdward')
para('La captura R1 Directa ON fue especialmente variable: mediana 283,15 ms y p95 619,34 ms; las medianas de sus tres pasadas fueron 288,31 / 284,23 / 230,72 ms. '+
     'Por ese motivo se realizó la tanda final y se evita presentar aquel factor de mejora como una promesa general. '+
     'La segunda tanda R2 solo completó drivers + salida wrinkles OFF (42,87 ms); quedó interrumpida por el fallo de exportación. No se ha mezclado con F1/F2.')
sub('Puertas de calidad')
old_quality=read(ROUTING/'comparison.json').get('quality',[])
para('R1: todos los prototipos frente a Directa dieron error máximo 0 en cuerpo, cabeza high y low y 23 prendas, con 1.092 muestras malla/pose por comparación. '+
     'Se probaron Parallel completo y controles de DG/Serial, ida y vuelta. Las wrinkles produjeron desplazamiento real de hasta 0,188163 unidades; no fue una prueba con efecto vacío.')
extended=[read(p) for p in sorted(FOLDER.glob('final_quality_*.json')) if 'variant' in read(p)]
if extended:
    table(['Prueba extendida','Wrinkles','Muestras malla/pose','Error máx.','Resultado'],[
        [LABELS[p['variant']],'ON' if p['wrinkles'] else 'OFF',p['samples'],num(max(p['max_error'].values()),8),'Pasa' if p['accepted'] else 'Diferencia']
        for p in extended if p['variant']!='direct'],[180,55,100,90,85])
    para('Puerta extendida: 18 módulos, 10 poses de ida y vuelta, Parallel CPU mediante cambios explícitos de controles. '+
         'Es una verificación adicional a los resultados R1 en varios modos; no certifica equivalencia en toda posible animación.','SmallEdward')

title('Calidad de CPU, GPU y caché','La referencia cambia la decisión')
para('La puerta inicial de caché comparaba C (GPU sin caché) con D (GPU y caché caliente), y encontró diferencias en los collares. '+
     'La comparación posterior B (Parallel CPU) frente a C también detectó esas diferencias. Por ello, la decisión final usa B como referencia '+
     'de geometría y verifica caché e híbrido por separado. Un modo más rápido que falla esa referencia no se presenta como mejora aprobada.')
table(['Ruta','Wrinkles','CPU vs GPU: error máx.','Resultado'],[
    [LABELS[p['variant']],'ON' if p['wrinkles'] else 'OFF',num(p['max_error'],8),'Diferencia' if not p['accepted'] else 'Pasa']
    for p in GPU_QUALITY],[180,65,145,120])
para('7 fotogramas de la animación nativa F2; 26 salidas; 182 muestras por comparación. El error se concentra en collar3 y collar2. '+
     'Cuerpo, cabeza high/low y las otras prendas coinciden en las muestras. Las mallas faciales adicionales no resuelven esa diferencia. '+
     'Las lecturas de vértices se realizaron fuera de los tiempos.','SmallEdward')
if RESOLUTION:
    sub('Contraste final contra CPU e híbrido de collares')
    table(['Candidato','Wrinkles','Error reproducción','Error tras editar','Veredicto'],[
        [('CPU referencia' if p['state']=='B' else p['state']+(' / collares CPU' if p['blocked_collars'] else ' / normal')),
         'ON' if p['wrinkles'] else 'OFF',num(max(p['errors']['play'].values()),8),num(max(p['errors']['edit'].values()),8),
         'Referencia' if p['state']=='B' else ('Pasa' if p['accepted'] else 'Diferencia')]
        for p in RESOLUTION],[160,55,105,105,85])
    para('El intento híbrido selecciona collar2_PRX y collar3_PRX y solicita deformerEvaluator(gpuBlockPolicy="on"). '+
         'La consulta posterior no devolvió un estado individual (None); no se afirma una partición verificada de esos nodos. No se quitan PRX, pesos, targets ni geometría. La puerta final incluye 11 saltos de fotograma ida/vuelta y '+
         'dos ediciones de claves (mandíbula y hombro), con los 26 outputs. La política nativa aplicada y sus consultas quedan en los JSON.','SmallEdward')
    hybrid=[p for k,p in PERF.items() if k.startswith('final_hybrid_')]
    table(['Prueba híbrida o CPU ON','Mediana ms/f','p95 ms/f'],[
        [p['label'].replace('final_hybrid_cpu_reference_',''),ms(p['timing']['median_ms']),ms(p['timing']['p95_ms'])] for p in hybrid],
        [310,100,100])
    valid=[p for p in RESOLUTION if p['state']!='B' and p['accepted']]
    para('D normal y D con bloqueo solicitado pasan la referencia CPU, con wrinkles OFF y ON. D normal ya coincide; el intento de bloqueo no corrigió C ni aportó ventaja frente a D normal.')

title('Wrinkles, modos de evaluación y caché','Uso del rig')
wrinkle_rows=[r for r in DATA['routes'] if r['variant']=='original']
if wrinkle_rows:
    table(['Escena Original','Mediana ms/f','p95 ms/f','FPS derivados'],[
        ['Wrinkles '+('ON' if r['wrinkles'] else 'OFF'),ms(r['median']),ms(r['p95']),num(1000/r['median'])] for r in wrinkle_rows],
        [220,100,100,90])
para('OFF conecta la salida primaria de correctivas a la cabeza final; ON conecta la salida del conversor Bifrost. '+
     'Los collares ya reciben la cara antes de wrinkles mediante EdwardWrinkles_PrimaryWorld. '+
     'La exportación de 6 nodos de wrinkles mide '+mib(PAYLOAD['wrinkles']['bytes'])+' MiB. Un nodo de grafo puede contener bastante más dato que muchos nodos aritméticos pequeños.','SmallEdward')
para('Configuración conservada del snapshot: Envelope 1; Depth 1,2; CompressionStart 0; CompressionRange 0,59; ManualActivation 0; '+
     'Forehead 3; Eyes 0; Cheeks 0,2; Nose 1; Chin 0. Las pruebas caracterizan ese preset, no todas las regiones a máxima intensidad.','SmallEdward')
if (FOLDER/'final_wrinkles_displacement.json').exists():
    wd=read(FOLDER/'final_wrinkles_displacement.json')
    para('Comprobación F2 de efecto real: el desplazamiento máximo entre wrinkles OFF y ON fue '+num(wd['max_displacement'],8)+
         ' unidades de escena sobre las 20 poses de ida/vuelta, fuera del cronómetro.','SmallEdward')
event_lookup={r['name']:r for r in PROFILES[1]['event_cpu']}
para('Profiler F2 ON, totales inclusivos en 48 fotogramas: traducción Maya a Bifrost '+num(event_lookup['Maya to Bifrost Mesh translation']['inclusive_us']/1000)+
     ' ms; conversión Bifrost a Maya '+num(event_lookup['bifrost to maya mesh conversion']['inclusive_us']/1000)+
     ' ms; Graph execution '+num(event_lookup['Graph execution']['inclusive_us']/1000)+
     ' ms. Los eventos pueden anidarse y solaparse: no se suman como tiempo de pared. Los datos apuntan a estudiar las conversiones de malla; no prueban que añadir un driver las elimine.','SmallEdward')
state_rows=[p for k,p in PERF.items() if k.startswith('final_states_')]
if state_rows:
    modes={'A':'DG / sin GPU','B':'Parallel CPU','C':'Parallel GPU','D':'Parallel GPU + caché caliente'}
    table(['Modo','Mediana ms/f','p95 ms/f','Pasadas ms'],[
        [modes[p['state']]+(' / ON' if 'wrinkles1' in p['label'] else ' / OFF')+(' / rep.' if 'bookend' in p['label'] else ''),ms(p['timing']['median_ms']),ms(p['timing']['p95_ms']),
         ' / '.join(ms(r['median_ms']) for r in p['runs'])] for p in state_rows],[220,85,85,120])
cache_path=FOLDER/'final_cache_quality.json'
if cache_path.exists():
    cq=read(cache_path)
    para('<b>Comparación inicial D frente a C:</b> error máximo '+num(cq['max_error'],8)+' unidades. '+safe(cq['scope'])+'. '+
         'La tabla anterior contiene el veredicto decisivo contra B (CPU), incluyendo el híbrido de collares.','SmallEdward')
    para('<b>Resultado final de caché:</b> D normal coincide exactamente con B tanto con wrinkles como sin ellos en los saltos y las dos ediciones probados. '+
         'C normal difiere en los collares. Por eso el fallo de la primera comparación D-C no se atribuye por sí solo a un error de la caché.','SmallEdward')
    for key in ('final_states_D','final_states_wrinkles1_D'):
        p=PERF[key]
        para('Primera pasada de calentamiento '+('ON' if 'wrinkles1' in key else 'OFF')+': '+num(p['warmup_seconds'])+
             ' s para 48 fotogramas; no incluye una posible espera posterior a cacheEvaluator. Las medianas de D corresponden a las pasadas calientes.','SmallEdward')
else:
    para('<b>Caché:</b> las cifras calientes describen repetición de una animación ya calculada. No hay una puerta final de invalidación aprobada en este informe; '+
         'no se recomienda activar Cached Playback como solución validada para todos los controles.')

title('Registro de pasos, pruebas y resultados','Trazabilidad')
ledger=[
 ('1. Snapshot y rutas','Se guardó Edward_baseline.mb antes de editar. Se inventariaron conexiones y pesos. El .ma original se conserva.'),
 ('2. Correctivas del cuerpo','Se comprobó salida raw del skin, cuerpo visible y driver. Diferencia cuerpo-driver 1,827831; cuatro targets a peso 1. Se distinguió el cambio artístico de la optimización.'),
 ('3. Cinco prototipos','Directa, driver corporal, facial, ambos y salida wrinkles. Conservaron drivers de pantalón y de otra superficie. Se guardaron .mb independientes.'),
 ('4. Calidad R1','Se extrajeron puntos fuera del cronómetro en 15 poses, ida/vuelta y varios modos. Todos los prototipos coinciden exactamente con Directa; Original difiere en cuerpo/ropa.'),
 ('5. Benchmark R1 y R2','Se midió OFF/ON, latencia de poses en tres variantes, y se inició una repetición. Se detectó dispersión; R2 incompleta no se mezcló con la tanda final.'),
 ('6. Inventario de datos','16.547 nodos, 18 módulos, 58 skins, 118 shapes. Se corrigió pertenencia anidada de cuello/cara e inclusión de SDK. Se extrajeron pesos mediante entrada primaria de Bifrost.'),
 ('7. Peso nativo','118 exportaciones estrictas y baked. Una exportación inicial de skin high con Bifrost cerró Maya. Se recuperó el snapshot; el proceso standalone posterior completó las 118 sin error.'),
 ('8. Workload completo','Se extendieron las poses a los 18 módulos, ambos lados, dedos, dientes y lengua. No se comparó esa animación como si fuera la R1.'),
 ('9. Congelación diagnóstica','La preparación de frozen masivo de mandíbula no finalizó; se cerró la instancia de pruebas y se recuperó. No hay un tiempo válido de esa ablación. Se usó Profiler por módulo.'),
 ('10. Preparación de poses','El resolvedor genérico repetía descubrimiento semántico por canal. Se cacheó solo durante la preparación del benchmark, sin cambiar el rig ni los valores de las poses.'),
 ('11. Profiler OFF/ON','48 fotogramas por captura, buffer ampliado y metadatos de saturación. Atribución de EvaluateNode por módulo exclusivo, utilidades compartidas y globales.'),
 ('12. Ablaciones controladas','Puenteos de skinning total, capas high/low, 23 PRX y 3 correctivas; referencias intercaladas. Pesos y targets permanecen en las copias.'),
 ('13. Tanda final','Se normalizó perspectiva, se repitieron rutas relevantes, modos de evaluación y LOD. Se conservan muestras, p95 y medianas de cada pasada.'),
 ('14. Entrega y recuperación','Informe PDF, datos JSON y panel interactivo; restauración de la escena de artista desde el snapshot, sin sobrescribir su .ma.'),
]
table(['Paso','Prueba / resultado'],ledger,[125,385])

title('Soluciones priorizadas y límites','Aplicación práctica')
table(['Prioridad','Acción','Evidencia / condición'],[
    ['1 / uso diario','Parallel CPU para posing; sin wrinkles mientras no se necesiten.','CPU OFF 40,81 ms; CPU ON 154,30 ms. GPU sin caché difiere en collar3/collar2. OFF debe puentear el grafo; conservar correctivas.'],
    ['1 / reproducción','Cached Playback caliente para la animación ya calculada.','D normal: 20,62 ms OFF / 23,20 ms ON. Coincide con CPU en 11 saltos y 2 ediciones; validar otras tomas/controles y considerar el coste de llenar la caché.'],
    ['1 / drivers','Escoger el prototipo con menor tiempo estable y misma geometría que Directa.','Comparativa final y repeticiones de Directa/facial. Revisar cambio artístico del cuerpo respecto al Original.'],
    ['2 / módulos','Optimizar los nodos dominantes del Profiler, por módulos.','18 módulos con payload y CPU. Menos nodos por sí solo no demuestra menos coste. Evitar congelación masiva como herramienta de análisis.'],
    ['2 / ropa','Revisar PRX y sus drivers con más peso en la evaluación.','Ablación de grupo y capturas CPU. Rehacer o reducir driver exige otra puerta de calidad de ropa y collares.'],
    ['2 / LOD','Mantener low res y considerar LOD de pelo/ropa durante posing.','Pruebas de low, pelo y curvas. High puede seguir requerido por los collares; apagar visibilidad no garantiza eliminar todo cálculo.'],
    ['3 / datos','Paquete high-only o publicación limpia, en copia.','Low añade geometría, 4 skins y una correctiva. El ahorro exacto en escena completa requiere comparar dos guardados equivalentes. No se ha certificado un paquete recortado.'],
    ['3 / datos de pelo','Estudiar un paquete de animación sin datos XGen, conservando la versión de render.','Payload XGen aislado cercano a 99 MiB; no es un delta exacto del archivo. No se ha eliminado ni medido una versión sin XGen.'],
    ['3 / capas faciales','Estudiar consolidar capas de skins si el coste se confirma.','Son deformaciones secuenciales; fusionarlas o recortar influencias puede cambiar el resultado. No se han fusionado pesos ni presentado como solución equivalente aprobada.'],
    ['3 / interacción','Explorar curveManager/prepoblación de controles.','Autodesk describe esta opción para evaluación interactiva; no está implementada ni medida aquí. No confundirla con el cache local del resolvedor de las pruebas.'],
    ['No adoptado','No añadir drivers por una ganancia pequeña ni usar el bloqueo ensayado como arreglo.','Las mallas nuevas no corrigieron el error CPU/GPU. El intento gpuBlockPolicy tampoco; la caché normal ya pasa la referencia CPU sin ese añadido.'],
],[65,190,255])
para('Las cifras de esta auditoría describen este equipo, cámara, shading, animación y versiones nativas. No cubren un render final, texturas activas, otras GPU, '+
     'todas las poses posibles ni el VRAM exacto por sistema. Las ablaciones son marginales y no aditivas. No hay medición válida del ahorro al eliminar cada módulo; '+
     'su coste se expresa como CPU inclusiva de nodos, con esa limitación indicada en la tabla.')
para('El CV y el p95 incluyen la variación natural entre poses, además del ruido de ejecución. Se valoran junto con las medianas de las pasadas y las referencias intercaladas; '+
     'no constituyen por sí solos una prueba de inestabilidad ni un intervalo de confianza.','SmallEdward')
para('Referencia para poda y prepoblación: <link href="https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Customizing/files/GUID-27845E36-B873-42EB-B06F-9FE983E1080D.htm" color="#156F78">Autodesk Evaluation Toolkit / evaluators</link>.','SmallEdward')

title('Archivos de evidencia y repetición','Entrega verificable')
para('Los datos completos permiten revisar las cifras sin depender de este texto. Los exports aislados se usan para medición de datos y no deben abrirse como sustitutos del rig completo.')
evidence=[
 ['Snapshot original','maya_tools/assets/Edward/experiments/driver_routing_20261015_v001/Edward_baseline.mb'],
 ['Prototipos de rig','Misma carpeta: Edward_direct.mb, Edward_body_driver.mb, Edward_face_driver.mb, Edward_shared.mb, Edward_shared_wrinkles.mb'],
 ['Inventario y pesos','full_audit_20261015_v001/catalog.json'],
 ['Tamaños y hashes','full_audit_20261015_v001/storage.json + storage_payloads/*.mb'],
 ['Muestras temporales','full_audit_20261015_v001/*.performance.json'],
 ['CPU por módulo/nodo','final_profile_wrinkles0/1.txt + .summary.json; metadatos .json'],
 ['Calidad','driver_routing_20261015_v001/*quality.json + .npz; full_audit_20261015_v001/final_quality_*.json'],
 ['Datos de este informe','full_audit_20261015_v001/report_data.json'],
 ['Scripts reproducibles','scripts/edward_driver_routing_trial.py, edward_rig_audit.py, edward_final_audit.py, maya_trial_client.py, summarize_edward_audit.py, build_edward_audit_report.py'],
]
table(['Contenido','Ruta relativa a C:/proyectos/auto-rig'],evidence,[130,380])
para('La carpeta full_audit_20261015_v001 está dentro de maya_tools/assets/Edward/experiments. Los informes guardan hashes del snapshot y del código, plugins, '+
     'unidades, configuración del visor, cadenas GPU, caché y fallbacks. Para repetir, usar otra versión de carpeta/recibos y una copia del snapshot; '+
     'no sobrescribir los resultados de esta tanda.')
para('Invocación de ejemplo (Maya interactivo con canal local 7002):','SmallEdward')
para('python scripts/maya_trial_client.py scripts/edward_final_audit.py tmp/nuevo_recibo.json --port 7002 --arguments &apos;{&quot;action&quot;:&quot;profiles&quot;}&apos; --timeout 7200','SmallEdward')
para('Snapshot SHA-256: '+safe(CAT['source_sha256']),'SmallEdward')

OUTPUT.parent.mkdir(parents=True,exist_ok=True)
doc=SimpleDocTemplate(str(OUTPUT),pagesize=A4,rightMargin=15*mm,leftMargin=15*mm,topMargin=18*mm,bottomMargin=23*mm,
                      title='Edward: auditoría de rendimiento y peso del rig',author='Auditoría técnica / Codex')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
reader=PdfReader(str(OUTPUT))
DATA['pdf_pages']=len(reader.pages)
DATA['created_local']=datetime.now().isoformat()
(FOLDER/'report_data.json').write_text(json.dumps(DATA,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'pdf':str(OUTPUT),'pages':len(reader.pages),'bytes':OUTPUT.stat().st_size,'best_wrinkles':LABELS[best]},ensure_ascii=False))
