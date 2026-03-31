import pytest
import os
from unittest.mock import MagicMock, patch

# --- CRITICAL: Mock Environment and Database BEFORE importing tasks ---
os.environ["ENV"] = "testing"

# We mock 'database', 'models', and 'boto3' so the Worker's top-level 
# code doesn't try to connect to AWS or Postgres during unit tests.
with patch('database.wait_for_db', return_value=True), \
     patch('database.SessionLocal'), \
     patch('database.engine'), \
     patch('boto3.client'):  # <--- NEW: Prevent AWS credential crashes
    import tasks

@patch('tasks.get_redis')
@patch('tasks.model') 
@patch('tasks.update_db_job') 
def test_transcribe_logic_flow(mock_update_db, mock_model, mock_get_redis, tmp_path):
    
    # 0. REDIS MOCK
    mock_redis_instance = MagicMock()
    mock_get_redis.return_value = mock_redis_instance

    # 1. SETUP
    fake_job_id = "test-123"
    fake_video = tmp_path / "test_video.mp4"
    fake_video.write_text("fake video content")

    # 2. MODEL MOCK: Simulate the Whisper AI output
    mock_segment = MagicMock()
    mock_segment.text = "Hello world"
    mock_segment.end = 10
    
    mock_info = MagicMock()
    mock_info.duration = 10

    # The new tasks.py expects exactly this tuple return
    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    # 3. EXECUTE
    result = tasks.transcribe(fake_job_id, str(fake_video))

    # 4. ASSERTIONS
    assert "Hello world" in result
    
    # Verify Redis progress updates were attempted
    assert mock_redis_instance.set.called 
    
    # Verify Database status updates were attempted
    assert mock_update_db.called
    
    print("\n✅ Unit Test Passed! DB, Redis, AWS, and AI Model successfully mocked.")