#!/usr/bin/env sh
# Fetch or build a YOLOv8 HEF and labels for Hailo-8/8L. No 'set -e'.

if command -v sudo >/dev/null 2>&1; then SUDO=sudo; else SUDO=""; fi

DEST_DIR="/opt/hailo/models"
TMP_DIR="${TMPDIR:-/tmp}/hailo_models_$$"
MODEL_NAME="${MODEL_NAME:-yolov8s}"
HAILO_TARGET="${HAILO_TARGET:-hailo8l}"  # set to 'hailo8' for 26 TOPS, 'hailo8l' for 13 TOPS
HEF_OUT="${DEST_DIR}/${MODEL_NAME}.hef"
LBL_OUT="${DEST_DIR}/coco_labels.txt"

printf "[*] Target: %s  Model: %s\n" "$HAILO_TARGET" "$MODEL_NAME"
printf "[*] Creating destination: %s\n" "$DEST_DIR"
$SUDO mkdir -p "$DEST_DIR"

if [ ! -f "$LBL_OUT" ]; then
  printf "[*] Installing COCO labels -> %s\n" "$LBL_OUT"
  $SUDO tee "$LBL_OUT" >/dev/null <<'EOF'
person
bicycle
car
motorcycle
airplane
bus
train
truck
boat
traffic light
fire hydrant
stop sign
parking meter
bench
bird
cat
dog
horse
sheep
cow
elephant
bear
zebra
giraffe
backpack
umbrella
handbag
tie
suitcase
frisbee
skis
snowboard
sports ball
kite
baseball bat
baseball glove
skateboard
surfboard
tennis racket
bottle
wine glass
cup
fork
knife
spoon
bowl
banana
apple
sandwich
orange
broccoli
carrot
hot dog
pizza
donut
cake
chair
couch
potted plant
bed
dining table
toilet
tv
laptop
mouse
remote
keyboard
cell phone
microwave
oven
toaster
sink
refrigerator
book
clock
vase
scissors
teddy bear
hair drier
toothbrush
EOF
else
  printf "[=] Labels exist at %s\n" "$LBL_OUT"
fi

if [ -f "$HEF_OUT" ]; then
  printf "[=] HEF already exists at %s\n" "$HEF_OUT"
  exit 0
fi

printf "[*] Attempting to fetch precompiled HEF (%s) from public sources...\n" "$HAILO_TARGET"
mkdir -p "$TMP_DIR"
cd "$TMP_DIR" || exit 1

BASE_S3="https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ModelZoo/Compiled/v2.16.0"
CANDIDATES="
${BASE_S3}/${HAILO_TARGET}/${MODEL_NAME}.hef
https://github.com/hailo-ai/hailo-rpi5-examples/releases/latest/download/${MODEL_NAME}_${HAILO_TARGET}.hef
https://github.com/hailo-ai/hailo_model_zoo/releases/latest/download/${MODEL_NAME}_${HAILO_TARGET}.hef
https://raw.githubusercontent.com/hailo-ai/hailo-rpi5-examples/main/models/${MODEL_NAME}_${HAILO_TARGET}.hef
"

DL_OK=0
for url in $CANDIDATES; do
  printf "[*] Trying: %s\n" "$url"
  curl -fL --connect-timeout 10 --max-time 300 -o "${MODEL_NAME}.hef" "$url" && DL_OK=1 && break
done

if [ "$DL_OK" -eq 1 ]; then
  printf "[+] Downloaded HEF. Installing to %s\n" "$HEF_OUT"
  $SUDO cp "${MODEL_NAME}.hef" "$HEF_OUT"
  $SUDO chmod 644 "$HEF_OUT"
  printf "[+] Done.\n"
  exit 0
fi

printf "[!] Could not fetch a precompiled HEF. Will try to build with Hailo Model Zoo if available.\n"

if ! command -v pip >/dev/null 2>&1; then
  printf "[*] Installing pip...\n"
  $SUDO apt-get update && $SUDO apt-get install -y python3-pip || true
fi

printf "[*] Creating venv under %s/venv\n" "$TMP_DIR"
python3 -m venv "$TMP_DIR/venv" || true
. "$TMP_DIR/venv/bin/activate" 2>/dev/null || true
pip install --upgrade pip || true
pip install hailo_model_zoo || true

if command -v hailo_model_zoo_download >/dev/null 2>&1; then
  hailo_model_zoo_download -n "$MODEL_NAME" || true
  hailo_model_zoo_compile -n "$MODEL_NAME" -t "$HAILO_TARGET" -o "$TMP_DIR/${MODEL_NAME}.hef" || true
fi

deactivate 2>/dev/null || true

if [ -f "$TMP_DIR/${MODEL_NAME}.hef" ]; then
  printf "[+] Built HEF via Model Zoo. Installing to %s\n" "$HEF_OUT"
  $SUDO cp "$TMP_DIR/${MODEL_NAME}.hef" "$HEF_OUT"
  $SUDO chmod 644 "$HEF_OUT"
  printf "[+] Done.\n"
  exit 0
fi

printf "[X] Failed to obtain a HEF automatically.\nNext:\n- Download from Hailo developer portal a %s HEF for model %s and place it at %s\n- Or build on a PC with the official Hailo SDK/Model Zoo and copy the .hef to the Pi.\n" "$HAILO_TARGET" "$MODEL_NAME" "$HEF_OUT"
exit 2
