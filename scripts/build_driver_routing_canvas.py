"""Embed completed Edward trial measurements in the managed analysis canvas."""
import json
from pathlib import Path

folder=Path(__file__).resolve().parents[1]/'maya_tools/assets/Edward/experiments/driver_routing_20261015_v001'
data=[]
for path in sorted(folder.glob('*.performance.json')):
    p=json.loads(path.read_text())
    if 'routing_variant' not in p:continue
    data.append({'variant':p['routing_variant'],'wrinkles':p['wrinkles_enabled'],'state':p['state'],'trial':path.stem.split('_')[-1].split('.')[0],'median':p['timing']['median_ms'],'p95':p['timing']['p95_ms'],'runs':[r['median_ms'] for r in p['runs']],'interaction':p['control_interaction']['timing']['median_ms'] if p['control_interaction']['timing'] else None,'file':path.name})
quality=json.loads((folder/'comparison.json').read_text()).get('quality',[])
target=Path('C:/Users/LaiaPeris/.cursor/projects/c-proyectos/canvases/edward-driver-routing.canvas.tsx')
code='''import {Stack,Row,H1,H2,Text,Table,BarChart,Button,useState,Callout,Divider,useHostTheme} from "cursor/canvas";
const DATA=__DATA__;
const QUALITY=__QUALITY__;
const LABELS:Record<string,string>={direct:"Directa",shared:"Drivers cuerpo + cara",shared_wrinkles:"Drivers + salida wrinkles",body_driver:"Solo driver cuerpo",face_driver:"Solo driver facial",original:"Original"};
const MODES:Record<string,string>={A:"DG",B:"Parallel CPU",C:"Parallel GPU",D:"Cached Playback"};
export default function EdwardRouting(){
 const t=useHostTheme();const [wrinkles,setWrinkles]=useState(false);const [mode,setMode]=useState("C");
 const available=Object.keys(MODES).filter(s=>DATA.some(r=>r.state===s&&r.wrinkles===wrinkles));
 const selected=available.includes(mode)?mode:available[0];
 const rows=DATA.filter(r=>r.state===selected&&r.wrinkles===wrinkles);
 const labels=rows.map(r=>LABELS[r.variant]+" / "+r.trial);
 const interactive=rows.filter(r=>r.interaction!==null);
 return <Stack gap={18} style={{padding:24,maxWidth:1150,margin:"0 auto",background:t.bg.editor,color:t.text.primary}}>
 <H1>Edward: rendimiento de los drivers</H1>
 <Text tone="secondary">Maya 2026 · Viewport 2.0 · i9-14900HX · RTX 5060 Laptop · 15 de octubre de 2026</Text>
 <Callout tone="info">Comparación con el mismo resultado: todas las variantes nuevas incluyen las correctivas corporales en el cuerpo final. La escena original solo las enviaba al cinturón. Cuatro targets a peso 1; diferencia máxima con el cuerpo original: 1,8278 unidades.</Callout>
 <Row gap={8}><Button onClick={()=>setWrinkles(false)} variant={!wrinkles?"primary":"secondary"}>Sin wrinkles</Button><Button onClick={()=>setWrinkles(true)} variant={wrinkles?"primary":"secondary"}>Con wrinkles</Button></Row>
 <Row gap={8} wrap>{available.map(s=><Button key={s} onClick={()=>setMode(s)} variant={selected===s?"primary":"secondary"}>{MODES[s]}</Button>)}</Row>
 <H2>Tiempo de reproducción por variante</H2>
 <Text tone="secondary" size="small">Eje X: variante y tanda. Eje Y: milisegundos por fotograma. Menor es mejor.</Text>
 <BarChart categories={labels} series={[{name:"Mediana (ms/fotograma)",data:rows.map(r=>r.median),tone:"info"}]} valueSuffix=" ms" height={300}/>
 <Text tone="tertiary" size="small">Fuente: pruebas interactivas guardadas en driver_routing_20261015_v001. Cada tanda: fotogramas 1–48, calentamiento completo, 8 fotogramas descartados por pasada y 3 pasadas medidas (120 muestras). currentTime + refresco VP2; incluye envío al visor. Geometría y Profiler fuera del cronómetro.</Text>
 <Table headers={["Variante / tanda","Mediana ms","p95 ms","Medianas de pasadas ms"]} rows={rows.map(r=>[LABELS[r.variant]+" / "+r.trial,r.median.toFixed(2),r.p95.toFixed(2),r.runs.map(v=>v.toFixed(2)).join(" · ")])} columnAlign={["left","right","right","left"]}/>
 {interactive.length>0&&<><Divider/><H2>Aplicar una pose completa y refrescar</H2><Text tone="secondary">Incluye cambiar varios canales mediante comandos; no representa arrastrar un único control ni es una medida de FPS.</Text><Table headers={["Variante / tanda","Mediana ms/pose"]} rows={interactive.map(r=>[LABELS[r.variant]+" / "+r.trial,r.interaction!.toFixed(2)])} columnAlign={["left","right"]}/></>}
 <Divider/><H2>Verificación de deformación</H2>
 <Table headers={["Variante","Wrinkles","Error máximo (unidades)","Muestras malla/pose","Resultado"]} rows={QUALITY.map(q=>[LABELS[q.variant],q.wrinkles?"Activos":"Desactivados",q.max_error.toExponential(2),q.mesh_pose_samples,q.accepted?"Coincide con directa":"Diferencia"])} />
 <Text tone="secondary" size="small">Cuerpo, cabeza alta y baja y 23 prendas. DG y Serial en poses de control; Parallel en las 15 poses de ida y vuelta. Tolerancia: 0,0001 unidades. Sin lectura de vértices dentro de los tiempos de reproducción.</Text>
 <H2>Qué comparte cada variante</H2>
 <Text>Directa: correctivas → malla final → PRX. Driver cuerpo: las 14 entradas corporales de PRX reciben el driver corregido. Driver facial: salida facial corregida → driver → wrinkles / cabeza final y conversión a mundo de collares. Salida wrinkles: añade una malla oculta entre el conversor y la cabeza final. Las 9 entradas de pantalón y las 4 de otra superficie conservan sus fuentes.</Text>
 <Text tone="tertiary" size="small">Los resultados Cached Playback requieren su prueba independiente de geometría. La activación y los presets se conservan. Los archivos nativos y los informes JSON permiten repetir la comparación.</Text>
 </Stack>;
}
'''
target.write_text(code.replace('__DATA__',json.dumps(data,separators=(',',':'))).replace('__QUALITY__',json.dumps(quality,separators=(',',':'))),encoding='utf-8')
print(target)
