import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from config import settings
from models.config import ModelConfig, TtsConfig
from services.config_service import ConfigService
from testing_db import create_test_engine


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    engine = create_test_engine(TEST_DATABASE_URL)
    ModelConfig.__table__.create(bind=engine)
    TtsConfig.__table__.create(bind=engine)
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    session = testing_session_local()
    ConfigService.invalidate_cache()
    try:
        yield session
    finally:
        session.close()
        ConfigService.invalidate_cache()
        TtsConfig.__table__.drop(bind=engine)
        ModelConfig.__table__.drop(bind=engine)


@pytest.mark.asyncio
async def test_model_config_cache_refreshes_after_service_update(db_session):
    """
    首次读取后应命中缓存；通过服务更新配置后，缓存也要同步成新值。
    """
    config_service = ConfigService(db_session)

    first_config = await config_service.get_model_config()
    assert first_config.model_name == settings.OPENAI_MODEL_NAME

    saved_config = db_session.execute(select(ModelConfig).limit(1)).scalar_one()
    saved_config.model_name = "db_changed_without_sync"
    db_session.commit()

    cached_config = await config_service.get_model_config()
    assert cached_config.model_name == settings.OPENAI_MODEL_NAME

    updated_config = await config_service.update_model_config(model_name="cache_synced")
    assert updated_config.model_name == "cache_synced"

    refreshed_config = await config_service.get_model_config()
    assert refreshed_config.model_name == "cache_synced"


@pytest.mark.asyncio
async def test_tts_config_update_syncs_cache_and_normalizes_parameters(db_session):
    """
    TTS 配置保存后，后续读取应直接拿到更新后的缓存值，并保留参数规整逻辑。
    """
    config_service = ConfigService(db_session)

    updated_config = await config_service.update_tts_config(
        model_name="qwen3-tts-flash",
        api_endpoint="https://dashscope.aliyuncs.com/api/v1/services/audio/tts",
        api_key="test_key",
        parameters={
            "voice": "",
            "provider": "",
            "language_type": "",
            "speed": 9,
        },
    )

    assert updated_config.model_name == "qwen3-tts-flash"
    assert updated_config.parameters["voice"] == "Cherry"
    assert updated_config.parameters["provider"] == "dashscope"
    assert updated_config.parameters["language_type"] == "Chinese"
    assert updated_config.parameters["speed"] == settings.TTS_DEFAULT_SPEED

    saved_config = db_session.execute(select(TtsConfig).limit(1)).scalar_one()
    saved_config.parameters = {"voice": "ManualChange", "speed": 1.25}
    db_session.commit()

    cached_config = await config_service.get_tts_config()
    assert cached_config.parameters["voice"] == "Cherry"
    assert cached_config.parameters["speed"] == settings.TTS_DEFAULT_SPEED
