# Transcription

keyup transcribes every call it receives with [Whisper](https://github.com/openai/whisper)
speech-to-text. Where Whisper runs is up to you: a fresh install transcribes on the keyup
host's CPU, and you can add an NVIDIA GPU, an Intel iGPU or NPU, or a Whisper server on
another machine.

The full reference, with measurements, is keyup's
[STT.md](reference/keyup/STT.md).

## How keyup picks a backend

The worker sends each call to a **backend**: a Whisper server (or in-process engine) listed in
**Admin → Backends**. Each backend has a `priority` (the **lowest number** is tried first) and a
`concurrency` (how many calls it takes at once). The router uses the healthy backend with the
lowest priority that has a free slot, and fails over to the next one when a backend is down or
busy. So a GPU at priority 5 with the CPU at priority 10 uses the GPU and falls back to the
CPU while the GPU host is rebooting.

!!! warning "`STT_BACKENDS` is a seed, read once"
    `STT_BACKENDS` in `.env` is copied into the backends table only while that table is
    empty, which in practice means on the first start. After that the table wins and editing
    `STT_BACKENDS` does nothing. Change backends in **Admin → Backends**: a change reaches the
    running worker in about ten seconds with no restart.

| Option | Runs on | Needs | Compose profile |
| --- | --- | --- | --- |
| [CPU](#cpu-the-default) (default) | a Speaches container beside the stack | cores and memory | `stt-cpu` |
| [NVIDIA GPU](#nvidia-gpu) | a Speaches CUDA container, on this host or another | NVIDIA driver and Container Toolkit | `stt-gpu`, with `compose.gpu.yaml` |
| [Intel iGPU or NPU](#intel-igpu-and-npu-openvino) | an OpenVINO container | an Intel Core Ultra-class CPU and its device nodes | `stt-openvino` or `stt-ovms` |
| [Another Whisper server](#a-whisper-server-elsewhere) | any machine | a server speaking the OpenAI audio API | none |

## CPU (the default)

[Speaches](https://github.com/speaches-ai/speaches) serves faster-whisper behind the OpenAI
audio API. A new install has it switched on: `.env.example` sets the profile, and the built-in
backend points at it.

```sh
# .env next to compose.yaml (the .env.example values)
COMPOSE_PROFILES=stt-cpu
STT_CPU_MODEL=Systran/faster-whisper-small
STT_BACKENDS=[{"name":"whisper","kind":"openai_compatible","base_url":"http://stt-cpu:8000","api_key":"","model":"Systran/faster-whisper-small","concurrency":2,"priority":10}]
```

```sh
docker compose up -d
docker compose ps stt-cpu             # "healthy" once the model is downloaded
curl -s localhost:8093/health         # STT_CPU_PORT, published on the loopback only
```

The container downloads `STT_CPU_MODEL` into its `sttcpu` volume on first start (about 500 MB
for `small`) and reports healthy only once the model is listed. `STT_CPU_MODEL` must be the
same string as the backend's `model`; change the two together.

**Sizing.** The model runs as int8 (`STT_CPU_COMPUTE_TYPE`) and holds about 1 GB of RAM. While
a call transcribes it keeps the cores it is given busy: a 4-second call took about 3 seconds on
a 6-core desktop. On a small host, set `STT_CPU_THREADS` so Postgres and ingest keep a core or
two (`0`, the default, lets the engine decide), and keep the backend's `concurrency` at 1 or
2. Larger models are more accurate and several times slower on a CPU; measure on your own
calls before moving up.

If transcription runs somewhere else, take `stt-cpu` out of `COMPOSE_PROFILES`, or keep it as
the low-priority fallback. Removing the profile does not stop a running container:
`docker compose stop stt-cpu`.

## NVIDIA GPU

A GPU is what makes the large models practical. The host with the card needs the NVIDIA
driver and the NVIDIA Container Toolkit; this must work first:

```sh
docker run --rm --gpus all ubuntu nvidia-smi
```

The image is built on CUDA 12.9, so the "CUDA Version" `nvidia-smi` reports should be 12.9 or
later.

**On the keyup host**, the optional overlay `compose.gpu.yaml` adds an `stt-gpu` service that
downloads `STT_GPU_MODEL` (default `Systran/faster-whisper-large-v3`, about 3 GB) on first
start:

```sh
# .env next to compose.yaml
COMPOSE_FILE=compose.yaml:compose.gpu.yaml
COMPOSE_PROFILES=stt-cpu,stt-gpu      # keep stt-cpu as the fallback, or drop it
```

`large-v3` in float16 needs roughly 4-5 GB of GPU memory; `STT_GPU_COMPUTE_TYPE=int8_float16`
halves that on a small card. `STT_GPU_COUNT` picks how many GPUs the service gets.

**On another machine**, run the same image by hand and download the model once:

```sh
docker run -d --gpus all -p 8000:8000 --restart unless-stopped \
  ghcr.io/speaches-ai/speaches:0.8.3-cuda
curl -X POST localhost:8000/v1/models/Systran/faster-whisper-large-v3
```

Either way, add a backend **ahead of** the CPU one (Admin → Backends, or `STT_BACKENDS` on a
fresh install):

```json
{"name":"gpu","kind":"openai_compatible","base_url":"http://stt-gpu:8000",
 "model":"Systran/faster-whisper-large-v3","concurrency":2,"priority":5}
```

For a GPU on another machine, use its address, e.g. `http://gpu.example.org:8000`.

## Intel iGPU and NPU (OpenVINO)

Intel Core Ultra processors have an integrated GPU and an NPU that can run Whisper through
OpenVINO. The keyup image itself carries none of Intel's drivers, so the accelerator gets its
own container. There are two:

| Profile | Server | Devices | Backend `kind` |
| --- | --- | --- | --- |
| `stt-openvino` | keyup's own OpenVINO GenAI sidecar | CPU, iGPU (`GPU`); NPU in principle | `openai_compatible` |
| `stt-ovms` | Intel's OpenVINO Model Server, two containers | iGPU and **NPU** | `ovms` |

On the hardware keyup was measured on, only the `stt-ovms` profile transcribed on the NPU.

### The host side

The device nodes must exist on the machine that runs Docker, and the container joins the group
that owns them:

```sh
ls -l /dev/dri /dev/accel
# crw-rw---- 1 root render 226, 128 ... /dev/dri/renderD128
# crw-rw---- 1 root render 261,   0 ... /dev/accel/accel0
getent group render
```

Set `RENDER_GID` in `.env` to that group's id (the example uses `992`). If Docker itself runs in
a VM, pass both device nodes through to it first. Without an NPU, comment the
`/dev/accel/accel0` line out of the `stt-openvino` service: Compose refuses to start a service
whose device node does not exist.

### The `stt-openvino` sidecar

```sh
# .env next to compose.yaml
COMPOSE_PROFILES=stt-openvino
OV_MODEL=OpenVINO/whisper-base-fp16-ov
OV_DEVICE=GPU                      # CPU | GPU | NPU | AUTO
RENDER_GID=992
```

```sh
docker compose up -d stt-openvino
docker compose logs -f stt-openvino     # first start downloads and compiles the model
curl -s localhost:8098/health
```

The health answer lists the devices OpenVINO can see. `["CPU"]` alone means the container
cannot open the device node (check `RENDER_GID`); an error in `detail` means a driver problem.
Then add a backend whose `model` is exactly `OV_MODEL`:

```json
{"name":"stt-openvino","kind":"openai_compatible","base_url":"http://stt-openvino:8000",
 "model":"OpenVINO/whisper-base-fp16-ov","concurrency":1,"priority":50}
```

!!! note "Which model"
    Left unset, `OV_MODEL` is `OpenVINO/whisper-medium-fp16-ov` (from keyup v0.1.1), which gave
    the best results in keyup's own measurements, at about 3x real time on an iGPU.
    `OpenVINO/whisper-base-fp16-ov`, used above, is faster and showed no catastrophic failures.
    `OpenVINO/whisper-large-v3-turbo-int8-ov`, the default in keyup v0.1.0, is faster still and
    hears some details the others miss, but collapses to a stock phrase on some long calls;
    choose it knowingly, and check an older `.env` for it. STT.md treats the iGPU as a
    supplement to a GPU server rather than a replacement.

The model and its compiled cache live in the `ovmodels` volume; keep it, or every start pays
the compile again.

### The `stt-ovms` profile (Intel's model server)

```sh
# .env next to compose.yaml
COMPOSE_PROFILES=stt-ovms,stt-openvino
OVMS_MODEL=OpenVINO/whisper-large-v3-turbo-fp16-ov
RENDER_GID=992
```

```sh
docker compose up -d stt-ovms-npu stt-ovms-gpu
docker compose logs -f stt-ovms-npu    # first start downloads and compiles (minutes on the NPU)
curl -s localhost:8097/v1/models       # NPU; 8094 is the GPU container
```

Register them with `kind` `ovms` and `model` set to the **served** name, the last part of
`OVMS_MODEL`:

```json
{"name":"ovms-npu","kind":"ovms","base_url":"http://stt-ovms-npu:8000",
 "model":"whisper-large-v3-turbo-fp16-ov","concurrency":1,"priority":40}
```

The OVMS backends accept **no prompt and no hotwords**, so the vocabulary settings below
(places and extra prompt) do nothing there. Details, measurements and NPU caveats are in
STT.md section 3.

## A Whisper server elsewhere

Any server that speaks the OpenAI audio transcription API works as an `openai_compatible`
backend: point `base_url` at it, set `model` to the name it serves, and `api_key` if it wants
one. Give it a lower priority number than the CPU fallback.

## Teaching it your system's words

Whisper does better when told what it is likely to hear. keyup builds a prompt from your
talkgroup names and units automatically; four settings add to it. The first three are also
in **Admin → Settings → Transcription**, where a value set wins over `.env`.

| `.env` | What it does |
| --- | --- |
| `STT_PLACES` | Comma-separated towns, campuses and landmarks, e.g. `STT_PLACES=Springfield,Shelbyville,State University`. Added to the prompt and the hotword list after the talkgroup and unit names, so they are spelled the local way. |
| `STT_PROMPT_EXTRA` | Free text appended to the prompt: agency names, callsigns, street names. |
| `STT_HALLUCINATION_PATTERNS` | Extra regular expressions, one per line, that mark a transcript as a hallucination (labelled `noise`, no text kept). Added to the built-in patterns for caption credits and sign-offs. Not in `.env.example`; add the line. |
| `STT_TEXT_REWRITES` | Fixes applied to every transcript: `pattern => replacement` rules, separated by `;`, case-insensitive. For a word Whisper keeps writing as something else, e.g. a short callsign that comes back as a web domain: `STT_TEXT_REWRITES='\bxcom(\.com)+\b => XCOM'`. Quote the value. Read at start-up only. |

The prompt is capped at 800 characters and filled talkgroup names first and places last, so a
long place list cannot crowd out channel names. Rewrites and hallucination patterns apply to
every backend, because they run on the text keyup gets back.

## Other knobs

| `.env` | Default | What it does |
| --- | --- | --- |
| `TRANSCRIBE_DEFAULT` | `true` | Whether a newly seen talkgroup is transcribed. Each talkgroup also has its own **Transcribe** switch on the Talkgroups page. |
| `TRANSCRIBE_MIN_SECONDS` | `0.75` | Shorter calls are squelch tails, which Whisper tends to hallucinate on; they are not sent. |
| `STT_LANGUAGE` | `en` | The language passed to Whisper. |
| `STT_VAD` | `true` | Voice-activity detection on every request; effectively required for calls this short. |
| `STT_WORKERS` | `2` | Transcription threads in the worker. |
| `STT_NORMALIZE` | `true` | Loudness-normalise the copy sent to Whisper (never the stored recording). |

## Sizing at a glance

| Setup | Memory | First download | Speed |
| --- | --- | --- | --- |
| CPU, `faster-whisper-small`, int8 | about 1 GB RAM | about 500 MB | a 4 s call in about 3 s on 6 cores |
| NVIDIA, `faster-whisper-large-v3`, float16 | 4-5 GB of GPU memory | about 3 GB | the practical choice for the large model |
| Intel iGPU, `whisper-base-fp16-ov` | | small | about 12x real time on an older Iris Xe iGPU |

Measure on your own calls before you commit to a model; STT.md section 3 has the numbers
behind this table.
