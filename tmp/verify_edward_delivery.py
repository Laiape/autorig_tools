import json
from pathlib import Path
from PIL import Image, ImageDraw
import pdfplumber
from pypdf import PdfReader

root = Path('C:/proyectos/auto-rig')
folder = root / 'tmp/pdfs/edward'
images = sorted(folder.glob('final-*.png'))
for start in range(0, len(images), 9):
    sheet = Image.new('RGB', (1350, 1980), '#d5d5d5')
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(images[start:start + 9]):
        im = Image.open(path).convert('RGB')
        im.thumbnail((440, 625))
        x, y = (index % 3) * 450, (index // 3) * 660
        sheet.paste(im, (x + (450 - im.width) // 2, y + 25))
        draw.text((x + 15, y + 5), path.stem, fill='black')
    sheet.save(folder / ('final-contact-%d.png' % (start // 9 + 1)))

pdf = root / 'output/pdf/edward-rig-audit.pdf'
reader = PdfReader(pdf)
out = {'pages': len(reader.pages), 'bytes': pdf.stat().st_size, 'outside_page_words': [], 'page_headers': []}
with pdfplumber.open(pdf) as doc:
    for index, page in enumerate(doc.pages, 1):
        words = page.extract_words()
        out['page_headers'].append({'page': index, 'first_lines': page.extract_text().splitlines()[:3]})
        for word in words:
            if word['x0'] < -0.5 or word['top'] < -0.5 or word['x1'] > page.width + 0.5 or word['bottom'] > page.height + 0.5:
                out['outside_page_words'].append({'page': index, 'text': word['text']})
evidence = root / 'maya_tools/assets/Edward/experiments/full_audit_20261015_v001'
out['data_keys'] = list(json.loads((evidence / 'report_data.json').read_text(encoding='utf-8')).keys())
data = json.loads((evidence / 'report_data.json').read_text(encoding='utf-8'))
out['data_counts'] = {key: len(data[key]) for key in ('modules', 'layers', 'routes', 'components', 'quality_resolution')}
assert len(data['modules']) == 18
assert len(data['layers']) == 12
assert len(reader.pages) == 19
assert not out['outside_page_words']
out['restoration'] = json.loads((root / 'tmp/edward_artist_restored_final_receipt.json').read_text(encoding='utf-8'))
assert out['restoration']['success']
assert out['restoration']['result']['all_original_prx_and_head_routes_match']
(root / 'tmp/edward_full_report_plan.json').write_text(json.dumps({
    'status': 'complete',
    'user_request': 'Desglose completo de rendimiento y peso del rig Edward, pruebas comparadas de drivers, skinning, capas faciales, PRX, correctivas y wrinkles; informe y soluciones.',
    'pdf': str(pdf),
    'canvas': 'C:/Users/LaiaPeris/.cursor/projects/c-proyectos/canvases/edward-driver-routing.canvas.tsx',
    'data': str(evidence / 'report_data.json'),
    'visual_qa': 'Latest 19 rendered pages inspected; no clipping, overlap or orphan pages.',
    'canvas_typecheck': 'tsc --noEmit: exit 0',
    'result': 'Parallel CPU without wrinkles: 40.81 ms/f. Hot Cached Playback: 20.62 ms/f OFF and 23.20 ms/f ON, exact against CPU in 11 jumps and 2 edits. Extra driver meshes show no stable benefit. Uncached GPU differs in collars; no hybrid adopted.',
    'restoration': out['restoration'],
    'pending': [],
    'production_modules_changed': False,
    'git_commit_or_push': False,
}, ensure_ascii=False, indent=2), encoding='utf-8')
(root / 'tmp/edward_final_delivery_qa.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False, indent=2))
