#!/usr/bin/env python3
"""Generate macOS application icon assets (.icns and .png) for Time Clock."""
from __future__ import annotations

import math
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path


def write_png(width: int, height: int, rgba_bytes: bytes, output_path: Path) -> None:
    """Write raw RGBA byte buffer to a valid PNG file using pure Python."""
    # PNG signature
    png = bytearray(b"\x89PNG\r\n\x1a\n")

    # IHDR chunk
    # Width (4), Height (4), Bit depth (1), Color type (1: 6=RGBA), Compression (1), Filter (1), Interlace (1)
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    png.extend(struct.pack(">I", len(ihdr_data)))
    png.extend(b"IHDR")
    png.extend(ihdr_data)
    png.extend(struct.pack(">I", ihdr_crc))

    # IDAT chunk: prepend filter byte 0 (None) to each scanline
    scanlines = bytearray()
    row_size = width * 4
    for y in range(height):
        scanlines.append(0)  # Filter type None
        scanlines.extend(rgba_bytes[y * row_size : (y + 1) * row_size])

    compressed = zlib.compress(bytes(scanlines), level=9)
    idat_crc = zlib.crc32(b"IDAT" + compressed)
    png.extend(struct.pack(">I", len(compressed)))
    png.extend(b"IDAT")
    png.extend(compressed)
    png.extend(struct.pack(">I", idat_crc))

    # IEND chunk
    iend_crc = zlib.crc32(b"IEND")
    png.extend(struct.pack(">I", 0))
    png.extend(b"IEND")
    png.extend(struct.pack(">I", iend_crc))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(png)


def render_clock_master(size: int = 1024) -> bytes:
    """Render a crisp, modern macOS clock icon buffer in RGBA format."""
    center = size / 2.0
    radius = size * 0.44

    # Output buffer
    buffer = bytearray(size * size * 4)

    # Color palette
    # Background squircle / circle: Deep Slate Blue #1E293B to #0F172A
    # Dial: Crisp White / Off-white #F8FAFC
    # Outer Bezel: Electric Blue Accent #3B82F6
    # Hour hand: #0F172A
    # Minute hand: #2563EB
    # Second hand: #EF4444 (Crimson)
    # Pivot: #1E293B and #EF4444 center dot

    # Pre-calculate hour tick angles (12 ticks)
    ticks = []
    for h in range(12):
        angle = math.radians(h * 30 - 90)
        is_cardinal = (h % 3 == 0)
        ticks.append((angle, is_cardinal))

    # Hand angles: ~10:10:35 for horological balance
    # Hour hand: 10 + 10/60 = 10.1667 -> 305 degrees
    hour_angle = math.radians(10.1667 * 30 - 90)
    # Minute hand: 10 + 35/60 = 10.5833 -> 63.5 degrees
    min_angle = math.radians((10.0 + 35.0 / 60.0) * 6 - 90)
    # Second hand: 35 seconds -> 210 degrees
    sec_angle = math.radians(35 * 6 - 90)

    hour_len = radius * 0.52
    min_len = radius * 0.76
    sec_len = radius * 0.82

    def point_line_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        dx = x2 - x1
        dy = y2 - y1
        l2 = dx * dx + dy * dy
        if l2 == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    for y in range(size):
        for x in range(size):
            idx = (y * size + x) * 4
            dx = x - center
            dy = y - center
            dist = math.hypot(dx, dy)

            # Outer squircle / rounded backdrop (smooth circle with shadow)
            if dist > radius + 8:
                # Transparent outside
                continue

            # Anti-aliased outer edge
            if dist > radius:
                alpha = max(0.0, min(1.0, (radius + 8 - dist) / 8.0))
                # Soft shadow
                buffer[idx] = 15
                buffer[idx + 1] = 23
                buffer[idx + 2] = 42
                buffer[idx + 3] = int(alpha * 70)
                continue

            # Outer bezel ring (Electric Blue gradient / rim)
            bezel_thickness = size * 0.035
            dial_radius = radius - bezel_thickness

            if dist > dial_radius:
                # Bezel color
                t = (dist - dial_radius) / bezel_thickness
                r = int(37 + (59 - 37) * t)
                g = int(99 + (130 - 99) * t)
                b = int(235 + (246 - 235) * t)
                buffer[idx] = r
                buffer[idx + 1] = g
                buffer[idx + 2] = b
                buffer[idx + 3] = 255
                continue

            # Inside dial face (#F8FAFC crisp white with subtle depth)
            dial_t = dist / dial_radius
            base_r = int(255 - dial_t * 12)
            base_g = int(255 - dial_t * 10)
            base_b = int(255 - dial_t * 6)

            pixel_r, pixel_g, pixel_b = base_r, base_g, base_b

            # 1. Hour Ticks
            for angle, is_cardinal in ticks:
                cos_a = math.cos(angle)
                sin_a = math.sin(angle)
                t_inner = dial_radius * (0.80 if is_cardinal else 0.85)
                t_outer = dial_radius * 0.93
                x1 = center + cos_a * t_inner
                y1 = center + sin_a * t_inner
                x2 = center + cos_a * t_outer
                y2 = center + sin_a * t_outer
                t_width = size * (0.016 if is_cardinal else 0.009)

                d = point_line_dist(x, y, x1, y1, x2, y2)
                if d < t_width:
                    aa = max(0.0, min(1.0, (t_width - d) / 1.2))
                    tick_r = 15 if is_cardinal else 71
                    tick_g = 23 if is_cardinal else 85
                    tick_b = 42 if is_cardinal else 105
                    pixel_r = int(pixel_r * (1 - aa) + tick_r * aa)
                    pixel_g = int(pixel_g * (1 - aa) + tick_g * aa)
                    pixel_b = int(pixel_b * (1 - aa) + tick_b * aa)

            # 2. Hour Hand (bold slate)
            hx2 = center + math.cos(hour_angle) * hour_len
            hy2 = center + math.sin(hour_angle) * hour_len
            hx1 = center - math.cos(hour_angle) * (radius * 0.1)
            hy1 = center - math.sin(hour_angle) * (radius * 0.1)
            h_width = size * 0.022
            d_h = point_line_dist(x, y, hx1, hy1, hx2, hy2)
            if d_h < h_width:
                aa = max(0.0, min(1.0, (h_width - d_h) / 1.2))
                pixel_r = int(pixel_r * (1 - aa) + 15 * aa)
                pixel_g = int(pixel_g * (1 - aa) + 23 * aa)
                pixel_b = int(pixel_b * (1 - aa) + 42 * aa)

            # 3. Minute Hand (accent blue)
            mx2 = center + math.cos(min_angle) * min_len
            my2 = center + math.sin(min_angle) * min_len
            mx1 = center - math.cos(min_angle) * (radius * 0.12)
            my1 = center - math.sin(min_angle) * (radius * 0.12)
            m_width = size * 0.016
            d_m = point_line_dist(x, y, mx1, my1, mx2, my2)
            if d_m < m_width:
                aa = max(0.0, min(1.0, (m_width - d_m) / 1.2))
                pixel_r = int(pixel_r * (1 - aa) + 37 * aa)
                pixel_g = int(pixel_g * (1 - aa) + 99 * aa)
                pixel_b = int(pixel_b * (1 - aa) + 235 * aa)

            # 4. Second Hand (vibrant red / orange)
            sx2 = center + math.cos(sec_angle) * sec_len
            sy2 = center + math.sin(sec_angle) * sec_len
            sx1 = center - math.cos(sec_angle) * (radius * 0.18)
            sy1 = center - math.sin(sec_angle) * (radius * 0.18)
            s_width = size * 0.007
            d_s = point_line_dist(x, y, sx1, sy1, sx2, sy2)
            if d_s < s_width:
                aa = max(0.0, min(1.0, (s_width - d_s) / 1.0))
                pixel_r = int(pixel_r * (1 - aa) + 239 * aa)
                pixel_g = int(pixel_g * (1 - aa) + 68 * aa)
                pixel_b = int(pixel_b * (1 - aa) + 68 * aa)

            # 5. Center Pivot Cap
            pivot_radius = size * 0.03
            if dist < pivot_radius:
                aa = max(0.0, min(1.0, (pivot_radius - dist) / 1.0))
                pixel_r = int(pixel_r * (1 - aa) + 239 * aa)
                pixel_g = int(pixel_g * (1 - aa) + 68 * aa)
                pixel_b = int(pixel_b * (1 - aa) + 68 * aa)
            elif dist < pivot_radius + 4:
                aa = max(0.0, min(1.0, (pivot_radius + 4 - dist) / 1.0))
                pixel_r = int(pixel_r * (1 - aa) + 15 * aa)
                pixel_g = int(pixel_g * (1 - aa) + 23 * aa)
                pixel_b = int(pixel_b * (1 - aa) + 42 * aa)

            buffer[idx] = pixel_r
            buffer[idx + 1] = pixel_g
            buffer[idx + 2] = pixel_b
            buffer[idx + 3] = 255

    return bytes(buffer)


def build_icon_assets(repo_root: Path) -> None:
    """Generate master PNG, iconset, and .icns file for macOS bundle."""
    assets_dir = repo_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    master_png = assets_dir / "AppIcon_1024.png"
    icon_png = assets_dir / "icon.png"
    icns_path = assets_dir / "AppIcon.icns"

    print("Rendering master 1024x1024 clock icon...")
    master_rgba = render_clock_master(1024)
    write_png(1024, 1024, master_rgba, master_png)

    # Also render a 256x256 icon.png for Tkinter window icon
    print("Rendering 256x256 window icon...")
    icon_rgba = render_clock_master(256)
    write_png(256, 256, icon_rgba, icon_png)

    # Use temporary directory for iconset
    with tempfile.TemporaryDirectory() as temp_dir:
        iconset_dir = Path(temp_dir) / "AppIcon.iconset"
        iconset_dir.mkdir(parents=True, exist_ok=True)

        specs = [
            ("icon_16x16.png", 16),
            ("icon_16x16@2x.png", 32),
            ("icon_32x32.png", 32),
            ("icon_32x32@2x.png", 64),
            ("icon_128x128.png", 128),
            ("icon_128x128@2x.png", 256),
            ("icon_256x256.png", 256),
            ("icon_256x256@2x.png", 512),
            ("icon_512x512.png", 512),
            ("icon_512x512@2x.png", 1024),
        ]

        print("Generating macOS iconset sizes...")
        for filename, px in specs:
            target_path = iconset_dir / filename
            if px == 1024:
                shutil.copyfile(master_png, target_path)
            else:
                # Use macOS sips to cleanly resample
                cmd = [
                    "sips",
                    "-z",
                    str(px),
                    str(px),
                    str(master_png),
                    "--out",
                    str(target_path),
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("Compiling AppIcon.icns using iconutil...")
        iconutil_cmd = ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)]
        subprocess.run(iconutil_cmd, check=True)

    print(f"Successfully generated:\n - {icns_path}\n - {icon_png}\n - {master_png}")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    build_icon_assets(repo_root)


if __name__ == "__main__":
    main()
