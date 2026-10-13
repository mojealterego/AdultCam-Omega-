import pytest
from adultcam.stream_control import StreamPolicy


def test_remote_plain_rtmp_not_allowed_even_if_operator_configures_it():
    with pytest.raises(ValueError):
        StreamPolicy.from_env('rtmp://relay.example.com/live')


def test_local_loopback_rtmp_allowed_for_private_acceptance():
    result = StreamPolicy.from_env('rtmp://127.0.0.1:19350/live')
    assert 'rtmp://127.0.0.1:19350/live' in result.allowed_servers


def test_remote_rtmps_is_allowed():
    result = StreamPolicy.from_env('rtmps://relay.example.com/live')
    assert 'rtmps://relay.example.com/live' in result.allowed_servers
