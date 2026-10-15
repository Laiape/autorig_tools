"""Build original red SVG icons and transparent 64px PNGs with Maya's Qt."""
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6 import QtCore, QtGui, QtSvg

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'maya_tools' / 'icons' / 'red'
RED = '#ed5656'
LIGHT = '#ffc1b5'

# Original 24px drawings. One consistent grid, rounded strokes and open shapes.
DRAWINGS = {
    'framework': '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><path d="M14 17.5h7m-3.5-3.5v7"/>',
    'character': '<circle cx="12" cy="6" r="3"/><path d="M5 21v-3a7 7 0 0 1 14 0v3M8 15l4 3 4-3"/>',
    'package': '<path d="m3 7 9-4 9 4v10l-9 4-9-4V7Zm0 0 9 4 9-4M12 11v10M7.5 5l9 4v4"/>',
    'model': '<path d="m12 3 9 5v8l-9 5-9-5V8l9-5Zm0 0v10m-9-5 9 5 9-5M12 13v8M3 16l9-3 9 3"/>',
    'rig': '<circle cx="6" cy="18" r="2.5"/><circle cx="12" cy="11" r="2.5"/><circle cx="18" cy="5" r="2.5"/><path d="m7.6 16.1 2.8-3.2m3.4-3.7 2.4-2.4M4 5h4M6 3v4m12 9h3m-1.5-1.5v3"/>',
    'guide': '<circle cx="12" cy="12" r="6"/><path d="M12 2v6m0 8v6M2 12h6m8 0h6"/><circle cx="12" cy="12" r="1" fill="' + LIGHT + '" stroke="none"/>',
    'controller': '<ellipse cx="12" cy="12" rx="10" ry="4.5"/><ellipse cx="12" cy="12" rx="4.5" ry="10"/><circle cx="12" cy="12" r="1.6" fill="' + LIGHT + '" stroke="none"/>',
    'pose': '<circle cx="13" cy="4" r="2"/><path d="m12 8-2 6 5 3 2 4M10 14l-4 7M3 9l7 1 5-2 5 3"/>',
    'picker': '<path d="M8 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v5M8 7h8M8 11h3m1 2 9 4-4 1-2 4-3-9Z"/>',
    'corrective': '<path d="M3 15c3-12 5 10 9-2S19 3 21 9M3 20h18M4 4h3m-1.5-1.5v3"/><circle cx="12" cy="13" r="2" fill="' + LIGHT + '"/>',
    'wrinkle': '<path d="M3 6c3-5 6 5 9 0s6 5 9 0M3 12c3-5 6 5 9 0s6 5 9 0M3 18c3-5 6 5 9 0s6 5 9 0"/>',
    'skin': '<path d="m4 6 8-3 8 3v12l-8 3-8-3V6Zm0 0 8 3 8-3M12 9v12M4 12l8 3 8-3M8 4.5v15m8-15v15"/>',
    'transfer': '<path d="M3 4h6v6H3zM15 14h6v6h-6zM13 5h4a3 3 0 0 1 3 3v3m-3-3 3 3 2-3M11 19H7a3 3 0 0 1-3-3v-3m-2 3 2-3 3 3"/>',
    'wrap': '<path d="M3 8c5-6 13-6 18 0M3 16c5 6 13 6 18 0M7 5c-5 5-5 9 0 14m10-14c5 5 5 9 0 14M3 12h18"/><circle cx="12" cy="12" r="3"/>',
    'bake': '<path d="M5 3v4m7-4v4m7-4v4M4 13h16v8H4zM3 10h18M8 17h8M9 7l3 3 3-3"/>',
    'simulation': '<path d="M2 12h4l3-8 5 16 3-8h5M3 4v3m18 10v3"/>',
    'import': '<path d="M4 14v6h16v-6M12 3v12m-5-5 5 5 5-5"/>',
    'export': '<path d="M4 14v6h16v-6M12 15V3M7 8l5-5 5 5"/>',
    'mirror': '<path d="M12 2v3m0 3v3m0 3v3m0 3v2M3 6l6 6-6 6V6Zm18 0-6 6 6 6V6Z"/>',
    'reload': '<path d="M20 9a8 8 0 1 0 0 7M20 3v6h-6"/>',
    'favorite': '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"/>',
    'search': '<circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/>',
    'tools': '<path d="m4 20 8-8m2-2 6-6M3 4l4 1 1 4 9 9a2 2 0 0 0 3-3l-9-9-4-1-3-2-1 1Zm0 16 2 1 3-3-2-2-3 3v1Z"/>',
    'curve': '<path d="M3 19C3 4 21 20 21 5M3 19l3-6M21 5l-3 6"/><rect x="1.5" y="17.5" width="3" height="3" rx=".5" fill="' + LIGHT + '"/><rect x="19.5" y="3.5" width="3" height="3" rx=".5" fill="' + LIGHT + '"/>',
}


def main():
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    font_file = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'arial.ttf'
    if font_file.is_file():
        QtGui.QFontDatabase.addApplicationFont(str(font_file))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, drawing in DRAWINGS.items():
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24">'
               '<g fill="none" stroke="' + RED + '" stroke-width="1.65" stroke-linecap="round" '
               'stroke-linejoin="round">' + drawing + '</g></svg>\n')
        (OUTPUT / (name + '.svg')).write_text(svg, encoding='ascii')
        renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode('ascii')))
        if not renderer.isValid():
            raise ValueError('Invalid SVG: ' + name)
        image = QtGui.QImage(64, 64, QtGui.QImage.Format_ARGB32_Premultiplied)
        image.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(image)
        renderer.render(painter)
        painter.end()
        if not image.save(str(OUTPUT / (name + '.png'))):
            raise RuntimeError('Could not save icon: ' + name)

    # A real contact sheet for checking recognition at shelf size.
    sheet = QtGui.QImage(840, 430, QtGui.QImage.Format_RGB32)
    sheet.fill(QtGui.QColor('#282828'))
    painter = QtGui.QPainter(sheet)
    painter.setFont(QtGui.QFont('Arial', 10))
    painter.setPen(QtGui.QColor('#dddddd'))
    painter.drawText(24, 28, 'AUTORIG TOOLS / RED ICON SYSTEM')
    for index, name in enumerate(DRAWINGS):
        x, y = 20 + (index % 8) * 104, 52 + (index // 8) * 116
        painter.drawImage(x + 20, y, QtGui.QImage(str(OUTPUT / (name + '.png'))))
        painter.drawText(QtCore.QRect(x, y + 70, 104, 24), QtCore.Qt.AlignCenter, name.replace('_', ' ').title())
    painter.end()
    sheet.save(str(OUTPUT / 'preview.png'))
    print('Generated {} original red SVG/PNG icons.'.format(len(DRAWINGS)))


if __name__ == '__main__':
    main()
