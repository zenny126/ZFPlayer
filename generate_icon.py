import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def create_zfp_icon(output_path="app_icon.ico"):
    size = 512
    # Create image with transparent background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Outer rounded squircle container
    padding = 24
    corner_radius = 110
    rect = [padding, padding, size - padding, size - padding]

    # Gradient background: Deep Dark Slate (#0D0E12 to #1A1C24)
    bg_base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_base)
    bg_draw.rounded_rectangle(rect, corner_radius, fill=(18, 20, 26, 255))
    
    # Add a glowing subtle accent ring
    ring_rect = [padding + 4, padding + 4, size - padding - 4, size - padding - 4]
    bg_draw.rounded_rectangle(ring_rect, corner_radius - 4, outline=(70, 130, 240, 90), width=6)

    img = Image.alpha_composite(img, bg_base)

    # 2. Draw crisp "ZFP" typography monogram
    draw = ImageDraw.Draw(img)
    
    # Try loading a system bold font (Segoe UI Bold, Arial Bold) or fallback to default
    font = None
    font_names = ["Segoe UI Bold.ttf", "segoeuib.ttf", "arialbd.ttf", "arial.ttf", "consola.ttf"]
    font_path = None
    for fn in font_names:
        win_font = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", fn)
        if os.path.exists(win_font):
            font_path = win_font
            break

    if font_path:
        font = ImageFont.truetype(font_path, 160)
    else:
        font = ImageFont.load_default()

    text = "ZFP"
    
    # Get text bounding box for accurate centering
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    text_x = (size - text_width) / 2 - bbox[0]
    text_y = (size - text_height) / 2 - bbox[1] - 10

    # Draw text glow effect
    glow_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    glow_draw.text((text_x, text_y), text, font=font, fill=(50, 160, 255, 180))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(15))
    img = Image.alpha_composite(img, glow_img)

    # Draw primary text (Clean white with subtle cyan accent)
    draw = ImageDraw.Draw(img)
    draw.text((text_x, text_y), text, font=font, fill=(245, 247, 255, 255))

    # Decorative Hi-Res audio wave dot accent under ZFP
    dot_y = text_y + text_height + 35
    dot_center_x = size / 2
    for offset in [-30, 0, 30]:
        r = 6 if offset == 0 else 4
        fill_col = (60, 170, 255, 240) if offset == 0 else (140, 160, 190, 180)
        draw.ellipse([dot_center_x + offset - r, dot_y - r, dot_center_x + offset + r, dot_y + r], fill=fill_col)

    # 3. Save as multi-resolution Windows .ICO file
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(output_path, format="ICO", sizes=icon_sizes)
    print(f"[+] Successfully generated icon: {output_path}")

if __name__ == "__main__":
    create_zfp_icon()
