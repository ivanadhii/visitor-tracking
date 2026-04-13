# Person Tracking — Pusdatin

Sistem monitoring CCTV berbasis AI untuk deteksi dan tracking orang secara real-time dari kamera Hikvision H.265 via RTSP.

---

## Stack

- **Backend** — FastAPI + OpenCV + YOLOv11n + ByteTrack
- **Frontend** — React + Vite + Tailwind + HLS.js
- **Proxy** — Nginx
- **Container** — Docker Compose (GPU: NVIDIA CUDA 12.4)

---

## Alur Sistem

```
1. RTSP URL
   streams.yaml / Web UI
         │
         ▼
2. StreamManager
   - baca streams.yaml
   - buat StreamPipeline + HLSWriter per stream
         │
         ├──────────────────────────────────┐
         ▼                                  ▼
3. StreamPipeline                    4. HLSWriter
   (thread per stream)                (mode tergantung detection)

   Detection ON:                      Detection ON → pipe mode
   - buka RTSP via OpenCV             - terima raw BGR bytes dari pipeline
   - baca frame 20fps                 - spawn FFmpeg subprocess:
   - setiap 200ms → YOLO inference      input: stdin (rawvideo bgr24)
   - draw bounding box di frame         output: /app/hls/{id}/*.ts + index.m3u8
   - simpan annotated frame bytes
   - setiap 100ms → kirim frame       Detection OFF → passthrough mode
     bytes ke HLSWriter               - spawn FFmpeg subprocess:
   - update stats (active_count dll)    input: RTSP langsung
                                        output: /app/hls/{id}/*.ts + index.m3u8
         │
         ▼
5. /app/hls/{stream_id}/
   ├── index.m3u8   (playlist, diupdate tiap ~1 detik)
   └── seg0.ts, seg1.ts, ...  (segment video ~1 detik)
         │
         ▼
6. Nginx
   location /hls/ → serve static dari volume hls_data
   (backend dan nginx share volume yang sama)
         │
         ├──────────────────────────────────┐
         ▼                                  ▼
7. HLS.js (browser)                  8. WebSocket
   - poll index.m3u8 tiap detik        - backend kirim stats tiap 500ms
   - download segment .ts terbaru      - frontend update panel kanan
   - decode + render di <video>          (active_count, track list)
   - latency ~3-5 detik
```

**2 jalur paralel yang independen:**
- **Video** → OpenCV → annotate → FFmpeg → HLS segments → Nginx → HLS.js
- **Stats** → YOLO results → WebSocket → panel kanan

---

## Quick Start

```bash
# GPU mode (default)
make rebuild

# CPU only / tanpa AI
make plain-build
```

### Perintah umum

```bash
make up              # start semua container
make down            # stop semua container
make rebuild         # stop → rebuild → start
make restart-backend # restart backend saja (tanpa rebuild)
make logs-backend    # tail log backend
make gpu-check       # cek CUDA tersedia di container
make tune            # apply perubahan bytetrack.yaml (restart backend)
make clean           # hapus container + volume + image
```

---

## Konfigurasi

### Streams — `data/streams.yaml`

```yaml
- id: abc123
  name: Lobby Utama
  url: rtsp://user:pass@192.168.1.10/stream
  detection: true
```

### Users — `data/userlist.yaml`

```yaml
- username: admin
  password: admin123
```

Kosongkan file (atau hapus) untuk disable login.

### Tuning tracker — `backend/bytetrack.yaml`

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `track_high_thresh` | 0.30 | Confidence minimum untuk track baru |
| `track_low_thresh` | 0.05 | Confidence minimum deteksi lemah |
| `new_track_thresh` | 0.35 | Confidence minimum inisialisasi track |
| `track_buffer` | 150 | Frame track dipertahankan saat orang hilang |
| `match_thresh` | 0.85 | IoU threshold matching |
| `fuse_score` | true | Gabung detection score + IoU (ultralytics >= 8.3) |

Setelah ubah `bytetrack.yaml`, cukup `make tune` — tidak perlu rebuild.

---

## Environment Variables

| Variable | Default | Keterangan |
|----------|---------|------------|
| `NO_AI` | `0` | Set `1` untuk disable YOLO (plain mode) |
| `HLS_DIR` | `/app/hls` | Direktori output HLS segments |
| `TRANSCODE_HLS` | `1` | Set `0` untuk copy codec tanpa transcode |
