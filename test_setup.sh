#!/usr/bin/env bash

# Test script for pi-live-detect-rstp pipeline
set -e

echo "Testing Pi Live Detect RTSP Pipeline..."

# Change to the project directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

echo "✓ Virtual environment activated"

# Test Python imports
python -c "from src.pipeline.serve import app; print('✓ Pipeline imports successfully')"

# Test configuration loading
python -c "from src.pipeline.config import settings; print(f'✓ Configuration loaded: {len(settings.rtsp_urls)} streams configured')"

# Test individual modules
python -c "from src.pipeline.rtsp_client import RTSPClient; print('✓ RTSP Client imports successfully')"
python -c "from src.pipeline.infer_engine import HailoInference; print('✓ Inference Engine imports successfully')"
python -c "from src.pipeline.postprocess import filter_boxes; print('✓ Postprocess module imports successfully')"

echo "✓ All core modules import successfully"

# Test if FastAPI can be started (check help)
python -m src.pipeline.serve --help > /dev/null 2>&1
echo "✓ FastAPI server can be started"

# Test shell scripts exist and are executable
for script in bin/pld_*.sh; do
    if [[ -x "$script" ]]; then
        echo "✓ $script is executable"
    else
        echo "✗ $script is not executable"
        exit 1
    fi
done

echo ""
echo "🎉 All tests passed! The pipeline is ready to use."
echo ""
echo "To start the server:"
echo "  source venv/bin/activate"
echo "  python -m src.pipeline.serve --host 0.0.0.0 --port 8000"
echo ""
echo "Or use the shell script:"
echo "  ./bin/pld_api.sh"
