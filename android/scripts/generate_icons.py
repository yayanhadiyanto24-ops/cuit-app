import os
import cairosvg

SOURCE = "assets/cuit-app-icon.svg"
SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}

for density, size in SIZES.items():
    folder = f"android/app/src/main/res/mipmap-{density}"
    os.makedirs(folder, exist_ok=True)
    cairosvg.svg2png(
        url=SOURCE,
        write_to=f"{folder}/ic_launcher.png",
        output_width=size,
        output_height=size,
    )
print("Generated launcher icons from the official CUIT SVG.")
