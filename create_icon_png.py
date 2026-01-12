#!/usr/bin/env python3
"""SVG'den PNG icon olustur."""
import os
import subprocess
import sys

# SVG dosya yolu
svg_path = "teslimat_planlama/static/description/icon.svg"
png_path = "teslimat_planlama/static/description/icon.png"

print(f"SVG: {svg_path}")
print(f"PNG: {png_path}")

# macOS'ta qlmanage veya sips kullanarak donusturme
try:
    # sips komutu (macOS built-in)
    cmd = [
        "sips", "-s", "format", "png",
        "-z", "256", "256",
        svg_path,
        "--out", png_path
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    print("PNG basariyla olusturuldu!")
    print(result.stdout)
except subprocess.CalledProcessError as e:
    print(f"Hata: {e}")
    print(f"stderr: {e.stderr}")
    sys.exit(1)
except FileNotFoundError:
    print("sips bulunamadi. Alternatif yontem deneniyor...")
    
    # Alternatif: Python PIL kullanarak basit bir PNG olustur
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # 256x256 boyutunda gradient background
        img = Image.new('RGB', (256, 256), color='#14b8a6')
        draw = ImageDraw.Draw(img)
        
        # Basit bir kamyon sekli ciz (placeholder)
        # Truck body
        draw.rectangle([100, 90, 190, 150], fill='#ffffff', outline='#0f766e', width=2)
        # Cabin
        draw.polygon([(65, 110), (65, 150), (105, 150), (105, 110), (90, 90), (70, 90)], 
                     fill='#ffffff', outline='#0f766e')
        # Wheels
        draw.ellipse([65, 140, 95, 170], fill='#1e293b', outline='#0f172a')
        draw.ellipse([155, 140, 185, 170], fill='#1e293b', outline='#0f172a')
        
        img.save(png_path, 'PNG')
        print(f"PNG basariyla olusturuldu (PIL): {png_path}")
    except ImportError:
        print("PIL/Pillow kurulu degil. SVG kullanilacak.")
        sys.exit(1)
