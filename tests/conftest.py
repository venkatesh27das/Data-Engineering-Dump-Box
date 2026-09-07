import pytest

from app.config.settings import Settings
from scripts.create_sample_workbooks import create_samples


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path / "data")


@pytest.fixture(scope="session")
def samples(tmp_path_factory):
    return {p.stem: p for p in create_samples(tmp_path_factory.mktemp("workbooks"))}
