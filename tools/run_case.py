#!/usr/bin/env python3
"""Run model-only PKOC cases without changing the frozen UNMIL study interface."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
from case_pipeline.runner import main
if __name__ == '__main__':
    raise SystemExit(main())
