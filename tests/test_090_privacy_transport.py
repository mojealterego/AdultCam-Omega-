"""Real FFmpeg synthetic video passes through black-only stream filter."""
import shutil
import subprocess
import sys
import pytest


@pytest.mark.skipif(shutil.which('ffmpeg') is None,reason='FFmpeg unavailable')
def test_generated_video_becomes_black_before_output():
    width,height,frames=64,64,3
    source=subprocess.run([
        shutil.which('ffmpeg'),'-hide_banner','-nostdin','-loglevel','error',
        '-f','lavfi','-i','testsrc2=size=64x64:rate=3',
        '-frames:v',str(frames),'-f','rawvideo','-pix_fmt','rgb24','pipe:1'
    ],capture_output=True,timeout=12,check=True)
    assert len(source.stdout)==frames*width*height*3
    assert any(source.stdout)
    protected=subprocess.run([
        sys.executable,'-m','adultcam.privacy_pipeline',
        '--width',str(width),'--height',str(height)
    ],input=source.stdout,capture_output=True,timeout=12)
    assert protected.returncode==0,protected.stderr.decode('utf-8','replace')
    assert protected.stdout==bytes(frames*width*height*3)
