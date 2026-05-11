"""Centralized project paths."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
CONFIGS_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"
VIDEOS_DIR = DATA_DIR / "videos"
MASKS_DIR = DATA_DIR / "masks"
MODEL_DIR = DATA_DIR / "models"
WEIGHTS_DIR = MODEL_DIR / "weights"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
TESTS_DIR = PROJECT_ROOT / "tests"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DB_PATH = PROJECT_ROOT / "parking.db"
EASYOCR_MODEL_DIR = PROJECT_ROOT / "easyocr_models"
