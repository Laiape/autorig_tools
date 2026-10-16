"""Render completed audit data in the managed standalone analytical canvas."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/full_audit_20261015_v001'
data=json.loads((FOLDER/'report_data.json').read_text(encoding='utf-8'))
data['exact']=json.loads((FOLDER.parent/'exact_optimization_20261015_v001/exact_report_data.json').read_text())
target=Path('C:/Users/LaiaPeris/.cursor/projects/c-proyectos/canvases/edward-driver-routing.canvas.tsx')
code='''import {Stack,Row,Grid,H1,H2,Text,Table,BarChart,Button,useState,Callout,Divider,Stat,Link,useHostTheme} from "cursor/canvas";
const DATA=__DATA__;
const LABELS:Record<string,string>={original:"Original",direct:"Directa",shared:"Driver cuerpo + cara",shared_wrinkles:"Drivers + salida wrinkles",body_driver:"Solo driver cuerpo",face_driver:"Solo driver facial"};
const f=(v:number,n=2)=>v.toLocaleString("es-ES",{minimumFractionDigits:n,maximumFractionDigits:n});
const mb=(v:number)=>f(v/1048576)+" MiB";
const kb=(v:number)=>f(v/1024,1)+" KiB";
export default function EdwardAudit(){
 const t=useHostTheme();const [tab,setTab]=useState("Optimización exacta");const [wrinkles,setWrinkles]=useState(true);const [cohort,setCohort]=useState("final2_component_");const [garmentGroup,setGarmentGroup]=useState("Todas");
 const exact=DATA.exact;
 const garmentRows=exact.meshes.filter(r=>r.clothing&&(garmentGroup==="Todas"||r.group===garmentGroup));
 const names:Record<string,string>={original:"Original",zero_influences:"Solo influencias cero",safe_full:"Limpieza exacta completa",math_static:"Cálculos + puntos estáticos",cache:"Caché caliente · descartada"};
 const routes=DATA.routes.filter(r=>r.wrinkles===wrinkles);
 const components=DATA.components.filter(r=>r.label.startsWith(cohort));
 const modules=[...DATA.modules].sort((a,b)=>(wrinkles?b.cpu_on:b.cpu_off)-(wrinkles?a.cpu_on:a.cpu_off));
 const payload=(label:string)=>DATA.storage.find(r=>r.label===label)!.bytes;
 const cpu=DATA.state_tests.find(r=>r.label==="final_states_B")!;
 const cachedOff=DATA.state_tests.find(r=>r.label==="final_states_D")!;
 const cachedOn=DATA.state_tests.find(r=>r.label==="final_states_wrinkles1_D")!;
 const groups=[['Modelo baked',payload('model_all_display_outputs')],['58 skins',payload('all_skinClusters')],['Correctivas',payload('all_corrective_blendShapes')],['Wrinkles',payload('wrinkles')]] as [string,number][];
 return <Stack gap={18} style={{padding:24,maxWidth:1220,margin:"0 auto",background:t.bg.editor,color:t.text.primary}}>
 <H1>Edward: rendimiento y peso del rig</H1>
 <Text tone="secondary">15 octubre 2026 · Maya 2026 · i9-14900HX · RTX 5060 Laptop · datos reales del snapshot</Text>
 <Row gap={8} wrap>{["Optimización exacta","Ropa y accesorios","Skins y correctivas","Resumen","Módulos","Capas faciales","Ablaciones","Drivers","Calidad","Evaluación y LOD","Plan de mejora"].map(x=><Button key={x} variant={tab===x?"primary":"secondary"} onClick={()=>setTab(x)}>{x}</Button>)}</Row>
 {tab==="Optimización exacta"&&<>
 <Callout tone="info">La variante guardada conserva las 60 mallas, los 58 skins, los 23 PRX, los 852 joints y los wrinkles originales. Reapertura e importación de pesos SKC: error máximo cero en posiciones, normales de vértice y matrices en las poses probadas. Se han comparado 4.080 muestras de malla por variante.</Callout>
 <Grid columns={3} gap={16}><Stat label="CPU sin wrinkles · original" value="35,27 ms/f"/><Stat label="CPU sin wrinkles · optimizado" value="31,05 ms/f"/><Stat label="Reducción de tiempo estable" value="11,9 %"/></Grid>
 <Text>Con wrinkles no se ha demostrado una ganancia estable: las referencias oscilaron entre 98,29 y 122,53 ms/f. Los wrinkles permanecen activados al guardar. La reducción sin wrinkles corresponde al mismo modo de detalle OFF disponible antes del cambio.</Text>
 <Row gap={8}><Button onClick={()=>setWrinkles(false)} variant={!wrinkles?"primary":"secondary"}>Wrinkles OFF</Button><Button onClick={()=>setWrinkles(true)} variant={wrinkles?"primary":"secondary"}>Wrinkles ON</Button></Row>
 <H2>Tiempo de pared en escenas nativas reabiertas</H2><Text tone="secondary" size="small">X: candidato. Y: mediana combinada, ms/f; menor es mejor. Fuente: nueva cohorte CPU Parallel, visor 1317 × 804, 48 fotogramas, tres pasadas por bloque; 360 muestras de referencia y 240 por candidato. Caché: diagnóstico incompleto.</Text>
 <BarChart categories={exact.timings.filter(r=>r.wrinkles===wrinkles&&r.candidate!=="cache").map(r=>names[r.candidate])} series={[{name:"Mediana ms/f",data:exact.timings.filter(r=>r.wrinkles===wrinkles&&r.candidate!=="cache").map(r=>r.median_ms),tone:"info"}]} valueSuffix=" ms/f" height={280}/>
 <Table headers={["Variante","Mediana ms/f","p95 ms/f","Bloques ms/f","Resultado"]} rows={exact.timings.filter(r=>r.wrinkles===wrinkles).map(r=>[names[r.candidate],f(r.median_ms),f(r.p95_ms),r.block_medians.map(v=>f(v)).join(" / "),r.verdict==="reference"?"Referencia":r.verdict==="gain_beyond_band"?"Mejora fuera de la banda":r.verdict==="diagnostic_only_cache_hung"?"No adoptar: calentamiento bloqueado":"Dentro de la variación"])} />
 <H2>Cambios aceptados y peso real</H2><Text>Se comparten 17 cálculos nativos idénticos de los labios, se sustituyen 5.451 curvas constantes del scalp por sus mismos valores y se retiran 474 influencias con peso exactamente cero en 9 skins. Todos los pesos positivos, incluso los muy pequeños, y las capas faciales se conservan. Ningún sistema de deformación se puentea en la escena final.</Text>
 <Table headers={["Archivo nativo completo","Nodos","MiB"]} rows={exact.saved.map(r=>[names[r.candidate]??r.candidate,r.nodes,mb(r.bytes)])}/>
 <Text>Original: 163,47 MiB; limpieza completa: 161,81 MiB. Ahorro de 1,67 MiB (1,02 %). La limpieza de curvas y cálculos por sí sola reduce datos, pero no ha mostrado una mejora estable de FPS.</Text>
 <Callout tone="warning">Retirar influencias cero ralentizó mucho la evaluación inmediatamente después de editar el skin; tras guardar y reabrir, la mejora OFF se repitió. Por eso la limpieza se entrega en una copia nativa validada y no se ejecuta automáticamente en la sesión del artista ni al terminar CREATE RIG.</Callout>
 <H2>Puertas de calidad y decisiones</H2><Table headers={["Prueba","Error posición","Error normal","Error joints","Resultado"]} rows={exact.quality.map(r=>[r.candidate,f(r.max_position_error,10),f(r.max_normal_error,10),f(r.max_joint_error,10),r.accepted?"Pasa en el alcance probado":"Descartada"])} />
 <Text>17 poses únicas y recorrido inverso, ambos lados, 18 módulos, manos, labios, párpados, torsiones y extremidades para ropa, y globalScale publicado. Los canales de escala no uniforme estaban bloqueados/conectados: no se declara esa cobertura. Error máximo adicional de normales por cara/vértice en reposo: {f(exact.persistence.max_face_vertex_normal_error,10)}; tolerancia predeclarada 0,0001. El detalle wrinkle probado desplaza hasta {f(exact.measured_wrinkle_displacement,6)} unidades.</Text>
 <Text>Los cinco intentos de reparto GPU conservaron errores de collares y uno de los intentos de aislamiento bloqueó la instancia de pruebas. La simplificación amplia de mandíbula se descartó por normales. La caché también queda fuera del perfil automático tras bloquearse una repetición, aunque las pasadas calientes completadas fueran rápidas.</Text>
 <H2>Guardar y recuperar los datos</H2><Text>El SKC exacto conserva pesos y máscaras DQ sin redondeo ni umbral. Incluye 48 skins de polígonos en 34 mallas; los otros 10 skins de curvas/superficies se mantienen en el .mb. Se ha corregido la detección de skins detrás de Bifrost y el reordenamiento innecesario de skins al importar. La prueba de Edward sustituye pesos en el grafo nativo existente; no certifica una reconstrucción completa del rig o de todos los deformadores desde SKC.</Text>
 <Text>Dos reconstrucciones de esta limpieza desde el snapshot conservan los datos y resultados; no equivalen a dos CREATE RIG completos. La escena del artista, incluidos sus cambios sin guardar, sigue abierta sin sustituir.</Text>
 <Text><Link href="C:/proyectos/auto-rig/autorig_tools/maya_tools/assets/Edward/scenes/Edward_working_v004.mb">Escena optimizada validada · v004</Link> · <Link href="C:/proyectos/auto-rig/autorig_tools/maya_tools/docs/rig_exact_optimization_results_20261015.md">Informe técnico y evidencia</Link></Text>
 </>}
 {tab==="Ropa y accesorios"&&<>
 <H2>Las 47 mallas de ropa y accesorios</H2><Text>Incluye cuerpo/ropa, las 9 piezas del grupo de botas y las 16 del grupo de tijeras/guantes. Las 60 salidas del personaje, incluidas estas 47 piezas, pasan la comparación de geometría y normales. Conservan las rutas originales de cuerpo, cabeza y cinturón.</Text>
 <Row gap={8} wrap>{["Todas","cuerpo_geo","botas_geo","tijeras_geo"].map(g=><Button key={g} onClick={()=>setGarmentGroup(g)} variant={garmentGroup===g?"primary":"secondary"}>{g}</Button>)}<Button onClick={()=>setWrinkles(!wrinkles)}>CPU con wrinkles {wrinkles?"ON":"OFF"}</Button></Row>
 <Text tone="secondary" size="small">Fuente: exportaciones nativas de las 60 mallas y Profiler del archivo optimizado reabierto, 48 fotogramas. CPU es EvaluateNode inclusivo de la cadena directa; no es tiempo de pared ni ahorro al quitar la pieza. Los drivers compartidos se muestran aparte.</Text>
 <Table headers={["Malla / pieza","Grupo","Vértices","Geometría MB","Cadena directa","CPU directa ms/f","CPU drivers compartidos ms/f"]} rows={garmentRows.map(r=>[r.label,r.group,r.vertices,mb(r.mesh_bytes??0),[...r.primary_chain].reverse().map(x=>x.node).join(" → ")||"Sin deformador directo",f(wrinkles?r.direct_cpu_1:r.direct_cpu_0,3),f(wrinkles?r.driver_cpu_1:r.driver_cpu_0,3)])}/>
 <H2>Fuentes de los 23 PRX</H2><Table headers={["PRX","Salida","Driver y bind originales","Payload nativo previo","CPU inclusiva ms/f"]} rows={exact.prx.map(r=>[r.node,r.geometry.join(", "),r.drivers.map(d=>d.geometry+" / "+d.bind).join("; "),kb(r.native_bytes??0),f(wrinkles?r.cpu_1:r.cpu_0,3)])}/>
 <Callout tone="info">cinturon3 conserva su driver corporal con padding/correctivas. El cuerpo visible y los otros PRX corporales mantienen sus rutas originales. Los collares conservan su fuente de cabeza; no se ha sustituido por el low res que fallaba la equivalencia.</Callout>
 <Text tone="secondary">MB es una copia evaluada sin rig, historial ni redes de materiales; sus tamaños incluyen cabeceras y no se suman como ahorro de la escena ni representan RAM. Los payloads PRX reutilizan las capturas nativas previas: su contenido se ha verificado sin cambios. Una exportación nativa aislada de skin hizo fallar la instancia de pruebas; no se inventan tamaños nativos nuevos para las filas que no se completaron.</Text>
 </>}
 {tab==="Skins y correctivas"&&<>
 <H2>Los 58 skins conservados</H2><Text>Influencias retiradas: solo columnas exactamente cero. El máximo real de influencias por punto y los métodos DQ/lineal no se reducen. El low facial conserva sus cuatro capas; eliminarlas no había demostrado una ganancia estable.</Text>
 <Button onClick={()=>setWrinkles(!wrinkles)}>CPU con wrinkles {wrinkles?"ON":"OFF"}</Button>
 <Table headers={["Skin","Infl. antes → después","Máx. real/punto","Método","CPU inclusiva ms/f","SKC exacto KiB","Nativo original KiB"]} rows={exact.skins.map(r=>[r.name,r.before+" → "+r.after,Math.max(...r.geometry.map(g=>g.maximum_actual_influences)),r.method===2?"DQ combinado":r.method===1?"DQ":"Lineal",f(wrinkles?r.cpu_1:r.cpu_0,3),r.exact_skc_bytes==null?"Curva/superficie en MB":kb(r.exact_skc_bytes),r.native_original_bytes==null?"No capturado":kb(r.native_original_bytes)])}/>
 <Text tone="secondary">SKC: bytes del registro JSON sparse sin geometría, con precisión nativa. Nativo original: captura anterior al cambio, otro formato y otro alcance. No se comparan como si uno fuera ahorro del otro. Los 10 skins de curvas/superficies no se exportan como pesos de malla poligonal.</Text>
 <H2>Correctivas y blendShapes</H2><Table headers={["BlendShape","Targets registrados","Payload nativo previo","CPU inclusiva OFF ms/f","CPU inclusiva ON ms/f"]} rows={exact.blends.map(r=>[r.name,r.targets.length,kb(r.native_bytes??0),f(r.cpu_0,3),f(r.cpu_1,3)])}/>
 <H2>CPU atribuida a los 18 módulos, original y optimizado</H2><Text tone="secondary" size="small">EvaluateNode inclusivo / 48 fotogramas; no sumable a tiempo de pared. Ambos perfiles reabren sus archivos nativos; no se perfila el estado inmediatamente posterior a editar el skin.</Text>
 <Table headers={["Módulo","Original OFF","Optimizado OFF","Original ON","Optimizado ON","Payload nativo original"]} rows={exact.modules.map(r=>[r.name,f(r.original_0,3),f(r.safe_full_0,3),f(r.original_1,3),f(r.safe_full_1,3),kb(r.payload_bytes)])}/>
 </>}
 {tab==="Resumen"&&<>
 <Grid columns={3} gap={18}><Stat label="Escena completa" value={mb(DATA.scene_bytes)}/><Stat label="Nodos inventariados" value={String(DATA.node_count)}/><Stat label="Sistemas" value="18 módulos / 58 skins"/></Grid>
 <Grid columns={3} gap={18}><Stat label="Posing CPU / wrinkles OFF" value={f(cpu.median_ms)+" ms/f"}/><Stat label="Caché caliente / OFF" value={f(cachedOff.median_ms)+" ms/f"}/><Stat label="Caché caliente / ON" value={f(cachedOn.median_ms)+" ms/f"}/></Grid>
 <Callout tone="warning">Auditoría inicial: GPU sin caché difiere de CPU en los collares. La caché coincidió en 11 saltos y 2 ediciones, pero una repetición posterior se bloqueó; no se adopta como perfil automático. Ver Optimización exacta para la decisión actual.</Callout>
 <Callout tone="info">Los prototipos de drivers cambiaban dónde se aplicaban las correctivas: la diferencia corporal fue de 1,827831 unidades. Se descartaron para preservar el rig. La escena optimizada conserva el padding exclusivo del cinturón y las demás rutas originales.</Callout>
 <H2>Datos nativos en disco</H2><Text tone="secondary" size="small">X: sistema exportado. Y: MiB medidos. Exportaciones aisladas, no aditivas a la escena ni equivalentes a RAM.</Text>
 <BarChart categories={groups.map(r=>r[0])} series={[{name:"Payload nativo (MiB)",data:groups.map(r=>r[1]/1048576),tone:"info"}]} valueSuffix=" MiB" height={290}/>
 <Table headers={["Sistema","Tamaño","Interpretación"]} rows={[["23 PRX",kb(payload('all_PRX')),"Parámetros; no incluye cachés de ejecución"],["Low res",mb(payload('model_cabeza_low')),"Geometría sin historial; 4 skins y una correctiva adicionales"],["Pelo poligonal",mb(payload('model_cabello_geo')),"41.208 vértices; candidato a LOD"]]}/>
 <Table headers={["Datos adicionales del modelo","Nodos","MiB nativos"]} rows={DATA.model_extras.map(r=>[r.label,r.nodes,mb(r.bytes)])}/>
 <Text tone="secondary">XGen ocupa cerca de 99 MiB aislados. Estos payloads pueden solapar datos y no se suman al .mb. Hay además 5.451 curvas de un solo key para puntos del scalp: 1,07 MiB; no se detectó EvaluateNode de ellas en estas capturas.</Text>
 <H2>Cómo usar el informe</H2><Text>Separar peso en disco, trabajo CPU inclusivo y tiempo por fotograma. Las ablaciones omiten deformación y solo localizan costes. Los deltas de sistemas en paralelo no se suman. El PDF contiene el inventario completo de 58 skins, PRX, correctivas, pasos, fallos y soluciones.</Text>
 <Text><Link href="C:/proyectos/auto-rig/output/pdf/edward-rig-audit.pdf">Abrir informe PDF completo</Link></Text>
 </>}
 {tab==="Módulos"&&<>
 <Row gap={8}><Button variant={!wrinkles?"primary":"secondary"} onClick={()=>setWrinkles(false)}>Profiler sin wrinkles</Button><Button variant={wrinkles?"primary":"secondary"} onClick={()=>setWrinkles(true)}>Profiler con wrinkles</Button></Row>
 <H2>CPU atribuida a los 18 módulos</H2><Text tone="secondary" size="small">X: módulo, ordenado por CPU. Y: ms CPU inclusivos por fotograma (EvaluateNode / 48 fotogramas). Fuente: capturas finales separadas del benchmark.</Text>
 <BarChart categories={modules.map(r=>r.name)} series={[{name:"CPU inclusiva (ms/f)",data:modules.map(r=>wrinkles?r.cpu_on:r.cpu_off),tone:"info"}]} valueSuffix=" ms CPU/f" height={360}/>
 <Callout tone="warning">Los eventos se solapan en paralelo y pueden anidarse. Estas cifras no son tiempo de pared ni ahorro al eliminar un módulo. La prueba de congelación masiva de mandíbula no produjo una medida válida.</Callout>
 <Table headers={["Módulo","Nodos exclusivos","Payload nativo","CPU OFF ms/f","CPU ON ms/f"]} rows={modules.map(r=>[r.name,r.nodes,kb(r.bytes),f(r.cpu_off,3),f(r.cpu_on,3)])} columnAlign={["left","right","right","right","right"]}/>
 </>}
 {tab==="Capas faciales"&&<>
 <H2>8 capas high y 4 capas low</H2><Text>High: 11.475 vértices por capa y 144.531 pesos no nulos. Low: 3.082 vértices por capa y 19.617 pesos no nulos. El low añade datos; su coste oculto depende de la poda y de los consumidores.</Text>
 <Table headers={["SkinCluster","Resolución","Influencias","Máx. real/v","Pesos no cero","Disco","Ahorro al puentear"]} rows={DATA.layers.map(r=>[r.name,r.resolution,r.influences,r.actual_max,r.weights,kb(r.bytes),r.delta])}/>
 <Text tone="secondary" size="small">* Diferencia dentro del mayor entre la deriva de referencias y el 5% de su mediana; no demuestra una mejora estable. Eliminar capas cambia la deformación. El PDF distingue ajuste de maxInfluences y valores realmente usados.</Text>
 </>}
 {tab==="Ablaciones"&&<>
 <Row gap={8}><Button onClick={()=>setCohort("final2_component_")} variant={cohort==="final2_component_"?"primary":"secondary"}>F2: perspectiva y FK fijados</Button><Button onClick={()=>setCohort("final_component_")} variant={cohort==="final_component_"?"primary":"secondary"}>F1: exploración y PRX individuales</Button></Row>
 <H2>Tiempo de pared al puentear deformadores</H2><Text tone="secondary">Cada fila: 120 muestras tras calentamiento. Milisegundos por fotograma; menor es mejor. Comparar con las referencias de la misma cohorte.</Text>
 <Table headers={["Prueba","Mediana ms/f","p95 ms/f","Pasadas ms","CV %"]} rows={components.map(r=>[r.label.replace(cohort,""),f(r.median),f(r.p95),r.runs.map(v=>f(v)).join(" / "),f(r.cv)])}/>
 <Callout tone="warning">Un puenteo elimina el algoritmo y cambia la geometría recibida por sistemas posteriores. Sirve para localizar coste; no es un rig final con calidad equivalente.</Callout>
 </>}
 {tab==="Drivers"&&<>
 <Callout tone="warning">Estos tiempos se tomaron con GPU; todas las rutas probadas mantienen la diferencia de los collares respecto a CPU. El driver facial muestra la menor cifra, pero su ventaja sobre Directa queda dentro de la deriva de repeticiones. No hay una mejora de calidad ni una ventaja estable que justifique añadirlo por velocidad.</Callout>
 <Row gap={8}><Button onClick={()=>setWrinkles(false)} variant={!wrinkles?"primary":"secondary"}>Sin wrinkles</Button><Button onClick={()=>setWrinkles(true)} variant={wrinkles?"primary":"secondary"}>Con wrinkles</Button></Row>
 <H2>Comparación final de rutas</H2><Text tone="secondary" size="small">X: variante y captura. Y: mediana ms/fotograma. Fuente: F2, 18 módulos, 48 fotogramas, 3 pasadas de 40 muestras útiles.</Text>
 <BarChart categories={routes.map(r=>LABELS[r.variant]+" / "+r.label.split("_")[2])} series={[{name:"Mediana ms/f",data:routes.map(r=>r.median),tone:"info"}]} valueSuffix=" ms/f" height={320}/>
 <Table headers={["Variante / captura","Mediana ms/f","p95 ms/f","Pasadas ms"]} rows={routes.map(r=>[LABELS[r.variant]+" / "+r.label.split("_")[2],f(r.median),f(r.p95),r.runs.map(v=>f(v)).join(" / ")])}/>
 <Text>Las variantes nuevas se verifican contra Directa; Original conserva otra salida corporal. Las repeticiones finales de Directa y driver facial permiten valorar la deriva. Los resultados R1, su latencia de poses y las verificaciones están en el PDF.</Text>
 </>}
 {tab==="Calidad"&&<>
 <H2>CPU frente a GPU, 26 salidas</H2><Table headers={["Variante","Wrinkles","Error máximo","Resultado"]} rows={DATA.gpu_quality.map(r=>[LABELS[r.variant],r.wrinkles?"ON":"OFF",f(r.max_error,8),r.accepted?"Pasa":"Diferencia en collares"])}/>
 <H2>Caché e intento híbrido contra CPU</H2><Table headers={["Candidato","Wrinkles","Error reproducción","Error al editar","Resultado"]} rows={DATA.quality_resolution.map(r=>[r.state+(r.blocked_collars?" / bloqueo PRX solicitado":" / normal"),r.wrinkles?"ON":"OFF",f(Math.max(...Object.values(r.errors.play)),8),f(Math.max(...Object.values(r.errors.edit)),8),r.state==="B"?"Referencia":r.accepted?"Pasa":"Diferencia"])}/>
 <Text>El intento de bloquear los dos PRX no corrigió la ruta GPU sin caché. D normal coincide exactamente con CPU en el alcance probado y evita ese añadido. Todas las variantes nuevas coinciden entre sí en la puerta CPU de 18 módulos; Original conserva otro resultado corporal.</Text>
 </>}
 {tab==="Evaluación y LOD"&&<>
 <H2>DG, CPU, GPU y caché caliente</H2><Table headers={["Prueba","Mediana ms/f","p95 ms/f","FPS derivados"]} rows={DATA.state_tests.map(r=>[r.label,f(r.median_ms),f(r.p95_ms),f(r.derived_fps)])}/>
 <H2>Opciones de visor y low res</H2><Table headers={["Prueba","Mediana ms/f","p95 ms/f"]} rows={DATA.display_tests.map(r=>[r.label,f(r.median_ms),f(r.p95_ms)])}/>
 <Text tone="secondary">Ocultar pelo puede podar su skin; ocultar curvas incluye controles y construcción. El low puede seguir necesitando la cabeza high para los collares. La caché solo se considera válida dentro del alcance de su puerta de geometría e invalidación descrita en el PDF.</Text>
 </>}
 {tab==="Plan de mejora"&&<>
 <H2>Configuración inicial implementada</H2>
 <Callout tone="info">Cada rig nuevo termina en Parallel CPU con GPU Override y Cached Playback desactivados. La creación conserva DG rápido. Una marca de datos en la raíz permite recuperar el perfil al abrir la escena con AutoRig Tools; las escenas antiguas sin marca no se migran automáticamente.</Callout>
 <Text>La configuración mantiene los ajustes artísticos y no calcula geometría, llena cachés ni ejecuta benchmarks. No se han regrabado todos los modelos. La prueba de configuración se mide aparte de un build completo y de su redibujado final.</Text>
 <Text tone="secondary">Validación: 19 pruebas nativas aprobadas. Registrar y aplicar el perfil en el fixture pequeño: 1,21 ms; aplicar los ajustes en Edward abierto: 0,29–0,55 ms en tres muestras. Estas cifras no incluyen un build completo ni su redibujado final.</Text>
 <H2>Orden de trabajo y puerta de aceptación</H2>
 <Table headers={["Fase","Estado","Acción","Aceptación"]} rows={[
 ["0 · Base de escena","Implementada","Perfil conservador al crear y abrir rigs marcados","Reapertura, idempotencia, errores y escenas ajenas verificados"],
 ["1 · CPU / GPU / caché","Medida · CPU retenida","GPU difiere en collares; caché tuvo un bloqueo","No activar automáticamente los perfiles descartados"],
 ["2 · Wrinkles","Prioridad alta","Bypass real del detalle; reducir conversiones Bifrost","Trabajo pesado ausente al desactivar y detalle correcto al restaurar"],
 ["3 · Módulos / ropa","47 piezas analizadas","17 cálculos idénticos compartidos; reescrituras mayores pendientes","Error cero en las poses probadas; 23 PRX conservados"],
 ["4 · Capas / peso","Limpieza exacta entregada","5451 curvas constantes y 474 dependencias cero retiradas","1,67 MiB menos; capas y pesos positivos conservados"],
 ["5 · Regresiones","Pasa para esta limpieza","Reapertura, dos reconstrucciones y pesos SKC; no dos CREATE RIG completos","60 mallas y 852 joints, wrinkles OFF/ON, sin diferencias"]
 ]}/>
 <H2>Qué significa puentear</H2><Text>Pasar temporalmente la geometría de entrada a la salida de un deformador para omitir su cálculo. También se omite su deformación: sirve para localizar costes, y solo se convierte en una solución si un reemplazo conserva el resultado. Los ahorros de varias pruebas no se suman.</Text>
 <H2>Criterios y skills del proyecto</H2>
 <Text><Link href="C:/proyectos/auto-rig/autorig_tools/maya_tools/docs/rig_performance_criteria.md">Criterios de rendimiento</Link> · <Link href="C:/proyectos/auto-rig/autorig_tools/maya_tools/docs/rig_optimization_roadmap_20261015.md">Plan completo de optimización</Link></Text>
 <Text><Link href="C:/proyectos/auto-rig/autorig_tools/.agents/skills/rig-change-impact/SKILL.md">Impacto de cambios grandes</Link> · <Link href="C:/proyectos/auto-rig/autorig_tools/.agents/skills/rig-performance-audit/SKILL.md">Auditoría de rendimiento</Link> · <Link href="C:/proyectos/auto-rig/autorig_tools/.agents/skills/rig-deformation-equivalence/SKILL.md">Equivalencia de deformación</Link></Text>
 <Text tone="secondary">Las prioridades son propuestas medibles: no se promete una ganancia de FPS antes de probar cada cambio. Los resultados de caché del snapshot de artista y de la anterior escena regional pertenecen a versiones distintas.</Text>
 </>}
 <Divider/><Text tone="tertiary" size="small">Fuentes: full_audit_20261015_v001/report_data.json y exact_optimization_20261015_v001/exact_report_data.json, dentro de C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments · 15 octubre 2026 · MiB = bytes / 1.048.576; KiB = bytes / 1.024. No combinar cohortes de tiempos. El .ma original se conserva.</Text>
 </Stack>;
}
'''
target.write_text(code.replace('__DATA__',json.dumps(data,separators=(',',':'),ensure_ascii=False)),encoding='utf-8')
print(target)
