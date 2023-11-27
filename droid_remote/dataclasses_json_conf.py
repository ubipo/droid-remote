from pathlib import Path
import dataclasses_json


def configure_dataclasses_json():
    dataclasses_json.cfg.global_config.encoders[Path] = str
    dataclasses_json.cfg.global_config.decoders[Path] = Path
