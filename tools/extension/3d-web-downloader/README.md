# 3D Web Downloader

Mendeteksi otomatis URL file 3D (GLB / glTF / USDZ) pada halaman web yang sedang
dibuka, menampilkan daftar detailnya, preview 3D interaktif (drag untuk orbit),
dan menyediakan tombol download.

## Install (development)

1. Buka `chrome://extensions`.
2. Aktifkan **Developer mode** (toggle kanan atas).
3. Klik **Load unpacked** dan pilih folder `tools/extension/3d-web-downloader/`.
4. Buka halaman web apa pun (mis. halaman Apple iPhone AR, Shopify 3D viewer,
   Sketchfab embed, atau halaman yang memuat `.glb`/`.gltf`/`.usdz`).
5. Klik ikon extension di toolbar Chrome — **side panel** akan terbuka dengan
   daftar aset yang terdeteksi.

> Setiap perubahan file: klik tombol **Reload** di `chrome://extensions` pada
> card extension ini, lalu buka side panel lagi.

## Cara pakai

- Tab **Assets** — daftar URL 3D yang terdeteksi (auto-refresh saat halaman
  berubah). Tiap item punya tombol **Preview** (GLB/glTF) dan **Download**.
- Tab **Preview** — pilih aset di dropdown, drag untuk memutar, scroll untuk zoom.
- Tab **Settings** — atur subfolder download dan toggle format yang dideteksi.
- Tab **Logs** — log aktivitas, filter dan autoscroll.

## Catatan teknis

- `vendor/` berisi Three.js + GLTFLoader + OrbitControls + RoomEnvironment +
  BufferGeometryUtils yang dibundle lokal (tanpa CDN) agar kompatibel dengan
  CSP MV3 `script-src 'self'`.
- Background script melakukan fetch blob untuk preview agar tidak terkendala
  CORS dari host publik.
- USDZ tidak bisa di-preview di Chrome — tombol Preview otomatis disabled,
  gunakan Download lalu buka dengan app AR (Quick Look di iOS / USDZ viewer).