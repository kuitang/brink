#!/usr/bin/env python3
"""Generate a simple mushroom cloud favicon."""

from PIL import Image, ImageDraw


def create_mushroom_cloud_favicon(size: int = 32) -> Image.Image:
    """Create a stylized mushroom cloud icon.

    Uses earth-tone palette matching the KoL-inspired theme.
    """
    # Create image with transparent background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Colors from our CSS theme (earth tones)
    cloud_color = (92, 74, 50, 255)  # --accent: #5c4a32
    stem_color = (139, 115, 85, 255)  # --border: #8b7355
    glow_color = (139, 58, 58, 200)  # --danger: #8b3a3a with alpha

    # Scale factors for different sizes
    s = size / 32

    # Draw the glow/explosion at base
    draw.ellipse([int(8 * s), int(22 * s), int(24 * s), int(30 * s)], fill=glow_color)

    # Draw the stem
    draw.polygon(
        [
            (int(14 * s), int(26 * s)),  # bottom left
            (int(18 * s), int(26 * s)),  # bottom right
            (int(20 * s), int(16 * s)),  # top right
            (int(12 * s), int(16 * s)),  # top left
        ],
        fill=stem_color,
    )

    # Draw the main cloud (top mushroom cap)
    draw.ellipse([int(4 * s), int(4 * s), int(28 * s), int(18 * s)], fill=cloud_color)

    # Add some cloud detail (smaller ellipses for texture)
    draw.ellipse([int(6 * s), int(6 * s), int(16 * s), int(14 * s)], fill=(102, 84, 60, 255))
    draw.ellipse([int(14 * s), int(8 * s), int(26 * s), int(16 * s)], fill=(82, 64, 40, 255))

    return img


def main():
    """Generate favicon files."""
    import os

    output_dir = os.path.join(os.path.dirname(__file__), "..", "src", "brinksmanship", "webapp", "static")

    # Generate different sizes

    # Create 32x32 as main favicon
    img_32 = create_mushroom_cloud_favicon(32)
    favicon_path = os.path.join(output_dir, "favicon.ico")

    # Save as ICO with multiple sizes
    img_16 = create_mushroom_cloud_favicon(16)
    img_48 = create_mushroom_cloud_favicon(48)

    img_32.save(favicon_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[img_16, img_48])
    print(f"Created: {favicon_path}")

    # Also save a PNG version
    png_path = os.path.join(output_dir, "favicon.png")
    img_32.save(png_path, format="PNG")
    print(f"Created: {png_path}")


if __name__ == "__main__":
    main()
